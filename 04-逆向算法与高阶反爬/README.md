# 04-逆向算法与高阶反爬 ⭐

## ⭐ 亮点文件：闲鱼数据获取.py

闲鱼（goofish.com）搜索接口数据采集，**逆向 mtop sign 签名算法**。

### 逆向目标

闲鱼搜索接口 `https://h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search/1.0/` 采用阿里 mtop 协议，请求需携带 `sign` 签名参数，否则返回 `FAIL_SYS_TOKEN_EXOIRED` 等错误。

### sign 算法还原

```
sign = MD5( token & timestamp & appKey & data )
```

1. **token 提取**：从 Cookie 中提取最后一个 `_m_h5_tk`，取 `_` 前半部分作为 token。
2. **timestamp**：13 位毫秒级时间戳 `int(time.time() * 1000)`。
3. **appKey**：闲鱼 PC 搜索固定值 `34839810`。
4. **data**：搜索 payload 的 JSON 字符串（含关键词、页码、排序等）。
5. **拼接加密**：`MD5(token & t & h & c_data)` 得到 32 位签名。

### 请求构造

- **请求头**：User-Agent + referer(`https://www.goofish.com/`) + cookie
- **payload**：pageNumber / keyword / rowsPerPage / sortValue 等字段转 JSON
- **参数**：sign / timestamp / appKey / data / api / v

### 技术要点

| 要点 | 说明 |
|------|------|
| token 滚动 | `_m_h5_tk` 会随请求刷新，需每次取最新值 |
| jsonpath 解析 | 用 `jsonpath` 提取嵌套返回数据 |
| CSV 落盘 | `csv` 模块写入搜索结果 |

> ⚠️ 代码中的 cookie 已脱敏为占位符，运行前需登录 goofish.com 并从浏览器复制你自己的 cookie（必须包含 `_m_h5_tk` / `sgcookie` / `tfstk` 等字段，否则 sign 计算会失败）。
