这是我的个人博客，博客地址是：https://ykiko.me

使用 Github Pages 进行部署，域名是在 Godaddy 上购买的，使用 Cloudflare 进行 CDN 加速。

使用的静态博客生成器是 [Hugo](https://gohugo.io/)，主题是 [blowfish](https://blowfish.page/)，使用的评论系统是 [giscus](https://giscus.app/zh-CN)，页面底部的看板娘来自于 [live2d](https://github.com/stevenjoezhang/live2d-widget)。

> 评论和看板娘的部署类似，都只要把相关的加载代码加入到页面的 footer 中即可。

一般来说，每当我写了一篇新文章之后，会把它发布到知乎上。之后的交流讨论和修改文章大多数时候也是在知乎上进行的。为了保证相关的修改能自动同步到博客，我写了一个爬虫脚本，每天自动爬取知乎上我的文章，进行同步。

> 目前 zhihu 加强了对爬虫的限制，正常的 API 没有 cookies 是没法请求成功的。这里我是使用了以前的 API 来绕过，不确定能坚持到什么时候。

博客有双语支持，但是考虑到我可能频繁修改文章，所以手动翻译不是一个好的选择。我一直在寻找一个比较靠谱的 AI 翻译来进行文章的批量翻译，但暂时还没有找到。如果找到了之后，可能也会把这些文章发布到 Reddit 上。

