const CUSTOMER_SITES = {
    // ---- 原有源 ----
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
    // ---- 2026-08-11 TVBox配置挖矿新增 ----
    guangsuapi: { api: 'https://api.guangsuapi.com/api.php/provide/vod/from/gsm3u8', name: '光速资源' },
    jszyapi: { api: 'https://jszyapi.com/api.php/provide/vod', name: '极速采集' },
    bfzyapi: { api: 'https://bfzyapi.com/api.php/provide/vod', name: '暴风资源' },
    xinlangapi: { api: 'https://api.xinlangapi.com/xinlangapi.php/provide/vod', name: '新浪资源' },
    hongniuzy2: { api: 'https://www.hongniuzy2.com/api.php/provide/vod', name: '红牛资源' },
    apibdzy: { api: 'https://api.apibdzy.com/api.php/provide/vod', name: '百度' },
    ffzyapi: { api: 'http://cj.ffzyapi.com/api.php/provide/vod', name: '非凡影视' },
    moduapi: { api: 'https://caiji.moduapi.cc/api.php/provide/vod', name: '魔都动漫' },
    huyaapi: { api: 'https://www.huyaapi.com/api.php/provide/vod/from/hym3u8', name: '琥珀影视' },
};


// 调用全局方法合并
if (window.extendAPISites) {
    window.extendAPISites(CUSTOMER_SITES);
} else {
    console.error("错误：请先加载 config.js！");
}
