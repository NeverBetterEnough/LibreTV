const CUSTOMER_SITES = {
    // qiqi 已移除 — API 超时不可用 (2026-08-09)
    hhzy: {
        api: 'https://hhzyapi.com/api.php/provide/vod',
        name: '豪华资源',
    },
    jyzy: {
        api: 'https://jyzyapi.com/provide/vod',
        name: '金鹰资源',
    },
    lzzy: {
        api: 'https://cj.lziapi.com/api.php/provide/vod',
        name: '量子资源',
    },
};

// 调用全局方法合并
if (window.extendAPISites) {
    window.extendAPISites(CUSTOMER_SITES);
} else {
    console.error("错误：请先加载 config.js！");
}
