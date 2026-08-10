// 按源搜索关键词，支持流式逐页回调
// 返回 { results, sourceName, ok }：
//   ok=false 表示源级失败（超时/网络错误/非200），results 为空
//   ok=true  表示源请求成功（可能 0 结果）
// 流式模式：传入 onPage(pageResults, apiName, apiId) 后，每页结果到达即回调
// （页1先返回并回调，额外页并行请求、随到随回调），调用方可边到边渲染
async function searchByAPIAndKeyWord(apiId, query, onPage = null) {
    let apiUrl, apiName, apiBaseUrl;

    // 处理自定义API
    if (apiId.startsWith('custom_')) {
        const customIndex = apiId.replace('custom_', '');
        const customApi = getCustomApiInfo(customIndex);
        if (!customApi) return { results: [], sourceName: '自定义源', ok: false };

        apiBaseUrl = customApi.url;
        apiUrl = apiBaseUrl + API_CONFIG.search.path + encodeURIComponent(query);
        apiName = customApi.name;
    } else {
        // 内置API
        if (!API_SITES[apiId]) return { results: [], sourceName: apiId, ok: false };

        apiBaseUrl = API_SITES[apiId].api;
        apiUrl = apiBaseUrl + API_CONFIG.search.path + encodeURIComponent(query);
        apiName = API_SITES[apiId].name;
    }

    // 为结果附加来源信息
    const decorate = (items) => items.map(item => ({
        ...item,
        source_name: apiName,
        source_code: apiId,
        api_url: apiId.startsWith('custom_') ? getCustomApiInfo(apiId.replace('custom_', ''))?.url : undefined
    }));

    try {
        // 页1（决定源是否可用，先到先回调）
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000);

        // 添加鉴权参数到代理URL
        const proxiedUrl = await window.ProxyAuth?.addAuthToProxyUrl
            ? await window.ProxyAuth.addAuthToProxyUrl(PROXY_URL + encodeURIComponent(apiUrl))
            : PROXY_URL + encodeURIComponent(apiUrl);

        const response = await fetch(proxiedUrl, {
            headers: API_CONFIG.search.headers,
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
            return { results: [], sourceName: apiName, ok: false };
        }

        const data = await response.json();

        // 处理第一页结果
        const results = [];
        if (data && data.list && Array.isArray(data.list) && data.list.length > 0) {
            const page1Results = decorate(data.list);
            results.push(...page1Results);
            if (onPage) onPage(page1Results, apiName, apiId);
        }

        // 获取总页数
        const pageCount = data.pagecount || 1;
        // 确定需要获取的额外页数 (最多获取maxPages页)
        const pagesToFetch = Math.min(pageCount - 1, API_CONFIG.search.maxPages - 1);

        // 额外页并行请求，逐页随到随回调（不等待全部完成）
        if (pagesToFetch > 0) {
            const additionalPagePromises = [];

            for (let page = 2; page <= pagesToFetch + 1; page++) {
                const pagePromise = (async () => {
                    try {
                        // 构建分页URL
                        const pageUrl = apiBaseUrl + API_CONFIG.search.pagePath
                            .replace('{query}', encodeURIComponent(query))
                            .replace('{page}', page);

                        const pageController = new AbortController();
                        const pageTimeoutId = setTimeout(() => pageController.abort(), 15000);

                        // 添加鉴权参数到代理URL
                        const proxiedPageUrl = await window.ProxyAuth?.addAuthToProxyUrl
                            ? await window.ProxyAuth.addAuthToProxyUrl(PROXY_URL + encodeURIComponent(pageUrl))
                            : PROXY_URL + encodeURIComponent(pageUrl);

                        const pageResponse = await fetch(proxiedPageUrl, {
                            headers: API_CONFIG.search.headers,
                            signal: pageController.signal
                        });

                        clearTimeout(pageTimeoutId);

                        if (!pageResponse.ok) return [];

                        const pageData = await pageResponse.json();

                        if (!pageData || !pageData.list || !Array.isArray(pageData.list)) return [];

                        // 处理当前页结果并逐页回调
                        const pageResults = decorate(pageData.list);
                        if (pageResults.length > 0) {
                            if (onPage) onPage(pageResults, apiName, apiId);
                        }
                        return pageResults;
                    } catch (error) {
                        console.warn(`API ${apiId} 第${page}页搜索失败:`, error);
                        return [];
                    }
                })();

                additionalPagePromises.push(pagePromise);
            }

            // 等待所有额外页完成（仅用于返回完整数组，回调已随到随发）
            const additionalResults = await Promise.all(additionalPagePromises);

            // 合并所有页的结果
            additionalResults.forEach(pageResults => {
                if (pageResults.length > 0) {
                    results.push(...pageResults);
                }
            });
        }

        return { results, sourceName: apiName, ok: true };
    } catch (error) {
        console.warn(`API ${apiId} 搜索失败:`, error);
        return { results: [], sourceName: apiName, ok: false };
    }
}
