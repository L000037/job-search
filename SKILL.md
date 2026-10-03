---
name: job-search
description: 端到端求职匹配，解析上传的简历（Word/PDF）生成结构化候选人画像，再根据用户给出的招聘网址和目标岗位类型抓取岗位、逐条阅读JD并按匹配度与成功率综合排序。当用户上传简历，或询问招聘网站上有哪些岗位/实习可以投递时使用；没有简历的泛职业咨询不要使用。
---

# 简历画像 → 岗位侦察综合排序（通用）

一条流水线：**简历解析 → 候选人画像 → 要招聘网址与岗位偏好 → 抓站逐个读 JD → 双维综合排序**。

## 阶段 0｜还没拿到简历：固定开场白

用户表达找工作/分析岗位意图但未提供简历时，原样回复，不展开：

> 请将你的简历发给我，告诉我招聘网址以及你心仪的岗位类型

## 阶段 1｜解析简历并生成画像

1. 用 Glob/LS 定位简历（`.docx/.doc/.pdf`，多份全部解析），运行：

```bash
python <本技能目录>/scripts/extract_resume.py "<简历绝对路径>"
```

   - docx 零依赖（直接解 zip 内 XML，含表格文字）；pdf 依赖 `pypdf`，缺失时脚本会提示 `pip install pypdf`。
   - `.doc`（旧格式）不支持，请用户另存为 docx/pdf。抽取为空/乱码时如实说明，**禁止编造简历内容**。
2. 严格按 [references/profile-template.md](references/profile-template.md) 生成画像，写入**工作区根目录 `candidate-profile.md`**；找不到的信息写"简历未体现"，短板必须诚实列出（后续评分的减分依据）。

   **画像分析的客观性要求（必须遵守）**
   - 只记录简历中可验证的事实：公司、时间、岗位、数字、奖项名称照抄，不夸大、不拔高、不补充简历没有的能力或经历。
   - 严格区分"简历明确写明"与"从经历推断"：推断内容必须用"推测/可能"标注，且只用于帮助理解，不计入硬事实。
   - 熟练度照抄简历措辞（了解/熟悉/熟练/精通），不得自行升级；工具和语言没有写就视为不会。
   - 用中性、第三人称陈述，禁用"优秀/突出/丰富经验/能力强"等主观褒奖词，以具体事实替代（写"独立交付5个项目按期上线"，不写"项目经验丰富"）。
   - 发现时间线矛盾、职责与头衔不符、成果无法归因到本人等疑点时，在画像中显式标注"存疑"并在简报中请用户确认，不得替用户圆场。
   - "已确认短板"一节对照用户目标岗位类型的高频要求逐项检查，客观列出缺失项，不因简历包装而省略。
3. 向用户简报画像要点并给出文件链接。若网址或岗位类型仍缺，再次询问：

> 画像已生成 ✅ 请把要分析的招聘网址发给我，并说明你心仪的岗位类型（可多个，例如：产品经理 / 软件交付经理 / 数据分析）

## 阶段 2｜岗位抓取

三类产物分区存放（**强制**，不得散落根目录）：

```text
<workspace>/
├── data/        <公司>_all_jobs.json（全量含JD）、<公司>_matched_jobs.json（筛选+评分）
├── fetchers/    <公司>.py（一站一个）
└── ranking/     <公司>.py、cross_company.py（多公司综合排序）
```

脚本一律用自身位置推导根目录，不硬编码绝对路径：
`ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`，再 `os.path.join(ROOT, "data", ...)`。
抓取代码从 [scripts/fetch_template.py](scripts/fetch_template.py) 复制改造，公司名用英文小写（baidu / kuaishou / mihoyo…）。

### 抓取手段（成本从低到高）

1. **WebFetch 列表页**：SSR 站点可直接拿到岗位与详情链接；SPA 空壳进入下一步。
2. **定位数据 API 重放**：下载首页 HTML → 找 JS bundle → 正则搜 `/api/`、`position`、`job`、`list`、`baseURL` → 用 curl.exe（Windows PowerShell 下 curl 是别名，必须用 curl.exe）或 requests 重放，分页抓全量，每页 sleep 0.5s。
3. **API 需登录态**：浏览器打开列表页 → `browser_evaluate` 注入 XHR/fetch 拦截器（代码见本文件末尾）→ **不要整页刷新**，点击筛选/分页触发请求 → 读 `window.__cap` 拿真实请求体 → Python 批量翻页。
4. **JD 详情**：优先确认列表接口是否已含完整 JD（很多站如此）；缺失时再抓详情，hash 路由详情页优先试 WebFetch；岗位 ID 多不连续，禁止遍历猜 ID。
5. **岗位直达链接（强制）**：每个岗位在落盘 JSON 中必须带 `job_url` 字段（完整绝对地址，含 `https://`）：
   - 优先取接口返回的详情链接字段（如 `positionUrl`/`detailUrl`）；
   - 否则用岗位 ID 按站点真实模板拼接（如 `https://jobs.mihoyo.com/#/campus/position/{id}`、快手 `.../#/position/detail/{id}?projectId=...`），模板必须来自浏览器地址栏或接口数据，不得猜测；
   - 实在拿不到的写 `null` 并在最终输出中显式注明"该岗无直达链接"，不得用列表页 URL 冒充。

### 已知站点参考（随用随补充）

| 站点 | 要点 |
|---|---|
| talent.baidu.com | `POST /httservice/getPostListNew`，form 表单：recruitType=INTERN/curPage/pageSize=10/keyWord/postType/workPlace/projectType；`status=='ok'`，data.list，字段 name/postType/workContent/serviceCondition/workPlace/projectType |
| campus.kuaishou.cn | `POST /recruit/campus/e/api/v1/open/positions/simple`，JSON 体含 recruitSubProjectCodes/pageNum/pageSize/positionCategoryCodes；类别码需带子类别展开串否则报 40014，子码从浏览器真实请求获取；`code==0`，list 内已含完整 JD |
| jobs.mihoyo.com | API 需鉴权；详情页 `/#/campus/position/{id}` 可被 WebFetch 渲染；ID 不连续；实习/应届是不同 project 通道，务必核对届次 |
| career.papegames.com | 校招岗可能整体下线；下线时检查社招路径但默认不适配在校生 |

## 阶段 3｜筛选（以用户心仪岗位类型为准，不写死方向）

1. 从用户给出的岗位类型构建关键词组：中文名 + 常见英文/缩写（如 产品经理→产品/PM/Product；软件交付经理→交付/项目经理/PMO/解决方案）。不确定覆盖范围时，列出关键词清单向用户确认一次。
2. 有岗位类别码的站点（如快手 J102x），从浏览器真实请求里确认类别与岗位的映射再筛。
3. 剔除测试岗（"勿投"）、明显无关职能；逐个确认：地点、招聘类型（日常实习/留用实习/应届/社招）、**届次**、学历、外语等。

## 阶段 4｜双维评分（0–100，规则通用，权重随画像动态调整）

读 `candidate-profile.md` 作为唯一事实来源。硬门槛（届次/学历/外语/年限/必备证书）任一不符：综合分上限 50 并标注原因。评分保持客观：画像"简历未体现"的能力一律按不具备处理，不因为岗位热门或候选人意愿强烈而抬分。

**匹配度**
- +30 核心经历逐条命中：把画像"核心经历/技能栈"拆成要素，与 JD 职责+要求逐条比对（方向越一致、成果越可迁移分越高）。
- +10 工具/技术栈命中；+5~10 学历专业对口；+5~10 证书荣誉与岗位相关（竞赛、语言成绩、行业认证）。
- 负向：画像"已确认短板"中列出的项被 JD 明确要求时 −10~30；纯执行岗与画像职级明显不符 −20。
- 评分理由必须引用 JD 原文要点与画像事实，不得套话。

**成功率 = 匹配度基线 + 竞争修正**
- +8~12 稀缺信号（JD 标注简历稀缺、B端/内部/PMO/基础设施类低关注岗）。
- −5~15 红海（热门 C 端、明星业务岗）。
- −10~25 画像中存在的明确硬伤（语言、特定行业经验、社招年限）。
- +5 留用实习/招多人/hot 新岗；同等匹配下留用实习对应届生战略价值更高。

**综合分 = 匹配度×0.55 + 成功率×0.45**。

## 阶段 5｜输出

1. 一句话：岗位池规模、筛选后数量、招聘季状态、用户心仪方向是否有对应岗。
2. 综合排序表（排名/公司/岗位/类型/地点/综合/匹配/成功率/直达链接）；用户要求时再拆成两张分榜。**岗位链接要求（跨客户端统一，不得省略）**：
   - 「岗位」列一律写成 Markdown 链接 `[岗位名](job_url)`，URL 必须是完整绝对路径；
   - 同时保留独立的「直达链接」列放**裸 URL** 作为兜底——部分客户端（如某些对话框/豆包等）不渲染表格单元格内的可点链接，裸 URL 至少可复制粘贴打开；
   - 两列数据同源，都取自 JSON 的 `job_url`，禁止一列有链接一列缺失；`job_url` 为 null 的岗位写"无"。
3. Top 3 逐条给出 JD ↔ 画像证据；保底岗、慎投岗（写清硬伤）。
4. 简历版本建议（若用户有多份简历）；投递数量/截止时间限制提醒。
5. 附 `data/`、`fetchers/`、`ranking/` 中的文件路径链接。
6. 多公司时额外输出跨公司综合榜，标注招聘类型与届次风险。

## 边界

- 不修改/移动简历原件；画像与分析产物只写在用户本地工作区。
- 用户更新简历后重跑阶段 1，覆盖更新 `candidate-profile.md`，旧排序需重新生成。

## 附录：XHR/fetch 拦截器（API 需登录态时注入）

```javascript
(function(){
  window.__cap = [];
  var o = XMLHttpRequest.prototype.open, s = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(m,u){ this.__u=u; this.__m=m; return o.apply(this,arguments); };
  XMLHttpRequest.prototype.send = function(b){
    var self=this;
    if(this.__u && this.__u.indexOf('position')>=0){
      this.addEventListener('load', function(){
        window.__cap.push({m:self.__m,u:self.__u,body:b,resp:self.responseText&&self.responseText.substring(0,3000)});
      });
    }
    return s.apply(this,arguments);
  };
  var f=window.fetch;
  window.fetch=function(i,init){
    var u=typeof i==='string'?i:i.url;
    if(u&&u.indexOf('position')>=0){
      return f.apply(this,arguments).then(function(r){
        r.clone().text().then(function(t){window.__cap.push({u:u,body:init&&init.body,resp:t.substring(0,3000)});});
        return r;
      });
    }
    return f.apply(this,arguments);
  };
  return 'ok';
})()
```
