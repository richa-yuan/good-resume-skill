#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""reactive-resume 数据校验 / ATS 扫描 / 渲染工具。

用法：
    python3 validate_resume.py validate <resume.json|career.json>   # schema 校验
    python3 validate_resume.py ats <resume.json>                    # ATS 扫描
    python3 validate_resume.py render <resume.json> [--format md|html] [--out 路径]

仅依赖 Python 3 标准库。退出码：0 = 通过（可有警告），1 = 存在错误。
"""

import argparse
import html as html_lib
import json
import re
import sys
from pathlib import Path

RESUME_SECTIONS = [
    "摘要", "社交", "经历", "教育", "项目", "技能", "语言", "兴趣",
    "奖项", "证书", "出版物", "志愿", "推荐人", "求职信",
]
STAGES = ["已投递", "筛选中", "面试中", "offer", "已结束"]
FIT_STATES = ["具备", "部分", "缺失"]
DATE_RE = re.compile(r"^\d{4}-\d{2}$")
PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")
LI_RE = re.compile(r"<li[^>]*>(.*?)</li>", re.S)
TAG_RE = re.compile(r"<[^>]+>")


# ---------- 通用工具 ----------

def load_json(path: Path):
    if not path.exists():
        return None, "文件不存在: %s" % path
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as e:
        return None, "JSON 解析失败（第 %d 行）: %s" % (e.lineno, e.msg)


def strip_tags(s: str) -> str:
    return html_lib.unescape(TAG_RE.sub("", s or "")).strip()


def bullets_of(desc: str):
    """从 HTML 描述中提取 <li> 文本；没有 <li> 时按行拆。"""
    items = [strip_tags(m) for m in LI_RE.findall(desc or "")]
    if not items and desc:
        items = [ln.strip("- •\t ") for ln in desc.splitlines() if ln.strip()]
    return [i for i in items if i]


def detect(data: dict) -> str:
    if not isinstance(data, dict):
        return "unknown"
    if "区块" in data or "基本信息" in data:
        return "resume"
    if "投递" in data or "职业档案" in data:
        return "career"
    return "unknown"


def report(title, errors, warnings):
    print("=" * 56)
    print(title)
    print("=" * 56)
    for e in errors:
        print("  [错误] %s" % e)
    for w in warnings:
        print("  [警告] %s" % w)
    if not errors and not warnings:
        print("  全部通过，零错误零警告。")
    print("-" * 56)
    print("  错误 %d 个，警告 %d 个 -> %s" % (
        len(errors), len(warnings),
        "不通过，请修复错误" if errors else "通过"))
    return 1 if errors else 0


# ---------- resume 校验 ----------

REQUIRED_ITEM_FIELDS = {
    "经历": ["公司", "职位", "开始"],
    "教育": ["学校", "学位", "专业"],
    "项目": ["名称"],
    "技能": ["名称"],
    "语言": ["语言", "流利度"],
    "兴趣": ["名称"],
    "奖项": ["标题", "颁奖方"],
    "证书": ["名称", "颁发机构"],
    "出版物": ["标题", "出版商"],
    "志愿": ["组织"],
    "推荐人": ["姓名"],
    "社交": ["网络", "用户名"],
    "摘要": ["内容"],
    "求职信": ["内容"],
}


def validate_resume(data: dict):
    errors, warnings = [], []

    if data.get("版本") != "1.0":
        warnings.append('顶层缺少 "版本": "1.0"')

    basics = data.get("基本信息")
    if not isinstance(basics, dict):
        errors.append('缺少 "基本信息" 对象')
    else:
        if not str(basics.get("姓名", "")).strip():
            errors.append('"基本信息.姓名" 为空')
        phone = str(basics.get("手机", ""))
        if phone and not PHONE_RE.match(phone):
            warnings.append('手机号格式异常: "%s"（ATS 解析可能失败）' % phone)
        email = str(basics.get("邮箱", ""))
        if email and not EMAIL_RE.match(email):
            warnings.append('邮箱格式异常: "%s"' % email)
        if not email:
            warnings.append('邮箱为空，ATS 与 HR 都需要')

    summary = data.get("个人摘要")
    if isinstance(summary, dict) and not summary.get("隐藏"):
        text = strip_tags(str(summary.get("内容", "")))
        if not text:
            warnings.append('"个人摘要" 为空')
        elif len(text) > 500:
            warnings.append("个人摘要 %d 字，偏长（建议 100-300 字）" % len(text))
        elif len(text) < 50:
            warnings.append("个人摘要仅 %d 字，信息量不足" % len(text))

    sections = data.get("区块")
    if not isinstance(sections, list) or not sections:
        errors.append('"区块" 必须是非空数组')
        sections = []

    seen_ids, seen_dates = set(), []
    for si, sec in enumerate(sections):
        tag = "区块[%d]" % si
        if not isinstance(sec, dict):
            errors.append("%s 不是对象" % tag)
            continue
        stype = sec.get("类型")
        if stype not in RESUME_SECTIONS:
            errors.append('%s 类型非法: "%s"（可用: %s）' % (tag, stype, "/".join(RESUME_SECTIONS)))
            continue
        items = sec.get("条目")
        if not isinstance(items, list):
            errors.append("%s（%s）缺少条目数组" % (tag, stype))
            continue
        if sec.get("隐藏"):
            continue
        for ii, item in enumerate(items):
            itag = "%s（%s）条目[%d]" % (tag, stype, ii)
            if not isinstance(item, dict):
                errors.append("%s 不是对象" % itag)
                continue
            iid = item.get("id")
            if iid:
                if iid in seen_ids:
                    warnings.append("%s id 重复: %s" % (itag, iid))
                seen_ids.add(iid)
            if item.get("隐藏"):
                continue
            for field in REQUIRED_ITEM_FIELDS.get(stype, []):
                val = item.get(field)
                if val is None or (isinstance(val, str) and not val.strip()):
                    errors.append('%s 缺少必填字段 "%s"' % (itag, field))
            for dk in ("开始", "结束"):
                if dk in item and item[dk] not in (None, "", "至今"):
                    if not DATE_RE.match(str(item[dk])):
                        errors.append('%s "%s" 日期格式应为 YYYY-MM，当前: "%s"' % (itag, dk, item[dk]))
                    elif item[dk] not in seen_dates:
                        seen_dates.append(item[dk])
            if item.get("结束") and item.get("开始") and str(item["结束"]) != "至今":
                try:
                    if item["结束"] < item["开始"]:
                        errors.append("%s 结束日期早于开始日期" % itag)
                except TypeError:
                    pass

    if not any(s.get("类型") == "经历" and s.get("条目") for s in sections if isinstance(s, dict)):
        warnings.append("没有任何工作经历条目——应届生可用项目/实习补足，但请确认是有意为之")

    return errors, warnings


# ---------- career 校验 ----------

def validate_career(data: dict):
    errors, warnings = [], []

    apps = data.get("投递")
    if apps is None:
        errors.append('缺少 "投递" 数组（没有投递记录时也应为 []）')
        apps = []
    if not isinstance(apps, list):
        errors.append('"投递" 必须是数组')
        apps = []

    for i, app in enumerate(apps):
        tag = "投递[%d]" % i
        if not isinstance(app, dict):
            errors.append("%s 不是对象" % tag)
            continue
        for field in ("公司", "职位", "阶段", "投递日期"):
            if not str(app.get(field, "")).strip():
                errors.append('%s 缺少 "%s"' % (tag, field))
        if app.get("阶段") not in STAGES:
            errors.append('%s 阶段非法: "%s"（可用: %s）' % (tag, app.get("阶段"), "/".join(STAGES)))
        d = str(app.get("投递日期", ""))
        if d and not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
            errors.append('%s 投递日期应为 YYYY-MM-DD: "%s"' % (tag, d))
        if app.get("阶段") == "已结束" and not str(app.get("备注", "")).strip():
            warnings.append("%s 已结束但未记录原因（复盘时会用到）" % tag)
        fit = app.get("匹配分析")
        if fit is not None:
            if not isinstance(fit, dict):
                errors.append("%s 匹配分析应为对象" % tag)
            else:
                for ri, req in enumerate(fit.get("要求", [])):
                    if req.get("状态") not in FIT_STATES:
                        errors.append('%s 匹配要求[%d] 状态非法: "%s"' % (tag, ri, req.get("状态")))
                    if req.get("状态") in ("具备", "部分") and not str(req.get("证据", "")).strip():
                        errors.append("%s 匹配要求[%d] 标为 %s 但没有证据" % (tag, ri, req["状态"]))

    for key in ("事实库", "故事库"):
        if key in data and not isinstance(data[key], list):
            errors.append('"%s" 应为数组' % key)

    profile = data.get("职业档案")
    if profile is not None and not isinstance(profile, dict):
        errors.append('"职业档案" 应为对象')

    return errors, warnings


# ---------- ATS 扫描 ----------

def ats_scan(data: dict):
    issues = []
    basics = data.get("基本信息") or {}
    if not str(basics.get("姓名", "")).strip():
        issues.append("姓名为空——ATS 解析的第一锚点")
    if not PHONE_RE.match(str(basics.get("手机", ""))):
        issues.append("手机号缺失或格式异常（应为 11 位纯数字，无分隔符）")
    if not EMAIL_RE.match(str(basics.get("邮箱", ""))):
        issues.append("邮箱缺失或格式异常")

    # 日期格式一致性
    fmts = set()
    for sec in data.get("区块", []):
        if not isinstance(sec, dict):
            continue
        for item in sec.get("条目", []):
            if not isinstance(item, dict) or item.get("隐藏"):
                continue
            for dk in ("开始", "结束"):
                v = item.get(dk)
                if v and str(v) != "至今":
                    fmts.add("YYYY-MM" if DATE_RE.match(str(v)) else "其他:%s" % v)
    if "其他" in " ".join(fmts):
        issues.append("存在非 YYYY-MM 格式的日期，请统一（%s）" % "、".join(sorted(fmts)))

    # bullet 质量
    for sec in data.get("区块", []):
        if not isinstance(sec, dict) or sec.get("类型") not in ("经历", "项目", "志愿") or sec.get("隐藏"):
            continue
        for item in sec.get("条目", []):
            if not isinstance(item, dict) or item.get("隐藏"):
                continue
            name = item.get("公司") or item.get("名称") or item.get("组织") or "?"
            bl = bullets_of(item.get("描述", ""))
            if not bl:
                issues.append("%s：描述为空或没有 <li> 列表" % name)
                continue
            no_digit = [b for b in bl if not re.search(r"\d", b)]
            if no_digit:
                issues.append("%s：%d/%d 条 bullet 不含数字（尽量量化，见 writing-playbook）" % (name, len(no_digit), len(bl)))
            long_b = [b for b in bl if len(b) > 120]
            if long_b:
                issues.append("%s：%d 条 bullet 超过 120 字，建议拆分" % (name, len(long_b)))

    # 篇幅估算（A4 单栏 10.5pt 约每页 2200 字符）
    total = 0
    for sec in data.get("区块", []):
        if isinstance(sec, dict) and not sec.get("隐藏"):
            for item in sec.get("条目", []):
                if isinstance(item, dict):
                    total += sum(len(b) for b in bullets_of(item.get("描述", "")))
    total += len(strip_tags(str((data.get("个人摘要") or {}).get("内容", ""))))
    pages = max(1, round(total / 2200 + 0.4))
    if pages > 2:
        issues.append("预估 %d 页——10 年内经验建议压到 1-2 页，删低含金量内容" % pages)
    else:
        issues.append("篇幅预估 %d 页，正常" % pages)

    return issues


# ---------- 渲染 ----------

def fmt_period(item):
    start, end = item.get("开始", ""), item.get("结束", "")
    if not start and not end:
        return ""
    start = str(start).replace("-", ".") if start else ""
    end = str(end).replace("-", ".") if end else "至今"
    return "%s – %s" % (start, end)


def render_md(data: dict) -> str:
    b = data.get("基本信息", {})
    contacts = " | ".join(x for x in [
        b.get("手机", ""), b.get("邮箱", ""), b.get("城市", ""),
        (b.get("个人网站") or {}).get("url", "")] if x)
    lines = ["# %s" % b.get("姓名", ""), ""]
    if b.get("头衔"):
        lines += ["**%s**" % b["头衔"], ""]
    if contacts:
        lines += [contacts, ""]
    s = data.get("个人摘要") or {}
    if s and not s.get("隐藏") and strip_tags(str(s.get("内容", ""))):
        lines += ["## %s" % s.get("标题", "个人简介"), "", strip_tags(str(s["内容"])), ""]
    for sec in data.get("区块", []):
        if not isinstance(sec, dict) or sec.get("隐藏") or not sec.get("条目"):
            continue
        stype = sec.get("类型")
        lines.append("## %s" % sec.get("标题", stype))
        lines.append("")
        for item in sec["条目"]:
            if not isinstance(item, dict) or item.get("隐藏"):
                continue
            if stype == "经历":
                head = "**%s** ｜ %s" % (item.get("公司", ""), item.get("职位", ""))
                if item.get("地点"):
                    head += " ｜ %s" % item["地点"]
            elif stype == "教育":
                head = "**%s** ｜ %s · %s" % (item.get("学校", ""), item.get("学位", ""), item.get("专业", ""))
                if item.get("成绩"):
                    head += "（%s）" % item["成绩"]
            elif stype == "项目":
                head = "**%s**" % item.get("名称", "")
                link = (item.get("网站") or {}).get("url", "")
                if link:
                    head += "（[%s](%s)）" % ((item.get("网站") or {}).get("label") or link, link)
            elif stype == "技能":
                kws = "、".join(item.get("关键词", []))
                head = "- **%s**：%s" % (item.get("名称", ""), kws)
                if item.get("熟练度"):
                    head += "（%s）" % item["熟练度"]
                lines.append(head)
                continue
            elif stype in ("语言",):
                lines.append("- **%s**：%s" % (item.get("语言", ""), item.get("流利度", "")))
                continue
            elif stype == "兴趣":
                lines.append("- **%s**：%s" % (item.get("名称", ""), "、".join(item.get("关键词", []))))
                continue
            elif stype == "奖项":
                head = "- **%s**（%s，%s）" % (item.get("标题", ""), item.get("颁奖方", ""), item.get("日期", ""))
                lines.append(head)
                continue
            elif stype == "证书":
                head = "- **%s**（%s，%s）" % (item.get("名称", ""), item.get("颁发机构", ""), item.get("日期", ""))
                lines.append(head)
                continue
            elif stype == "出版物":
                head = "- **%s**（%s，%s）" % (item.get("标题", ""), item.get("出版商", ""), item.get("日期", ""))
                lines.append(head)
                continue
            elif stype == "志愿":
                head = "**%s** ｜ %s" % (item.get("组织", ""), item.get("地点", ""))
            elif stype == "推荐人":
                head = "- **%s**（%s）—— 可应要求提供" % (item.get("姓名", ""), item.get("职位", ""))
                lines.append(head)
                continue
            elif stype == "社交":
                w = item.get("网站") or {}
                lines.append("- **%s**：%s（%s）" % (item.get("网络", ""), item.get("用户名", ""), w.get("url", "")))
                continue
            elif stype == "摘要":
                lines += [strip_tags(str(item.get("内容", ""))), ""]
                continue
            elif stype == "求职信":
                lines += ["### %s" % item.get("收件人", ""), "", strip_tags(str(item.get("内容", ""))), ""]
                continue
            else:
                head = "- %s" % item.get("标题", item.get("名称", ""))
            period = fmt_period(item)
            if period and stype in ("经历", "教育", "项目", "志愿"):
                head += " ｜ %s" % period
            lines.append(head)
            for bl in bullets_of(item.get("描述", "")):
                lines.append("  - %s" % bl)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_html(data: dict) -> str:
    md = render_md(data)
    b = data.get("基本信息", {})
    accent = (data.get("排版") or {}).get("主色", "#2f6feb")
    body = []
    body.append('<div class="page">')
    body.append('<h1>%s</h1>' % html_lib.escape(b.get("姓名", "")))
    if b.get("头衔"):
        body.append('<p class="headline">%s</p>' % html_lib.escape(b["头衔"]))
    contacts = [x for x in [b.get("手机", ""), b.get("邮箱", ""), b.get("城市", ""),
                            (b.get("个人网站") or {}).get("url", "")] if x]
    if contacts:
        body.append('<p class="contacts">%s</p>' % html_lib.escape(" | ".join(contacts)))
    for line in md.splitlines():
        if not line.strip():
            continue
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            body.append("<h2>%s</h2>" % html_lib.escape(line[3:]))
        elif line.startswith("  - "):
            body.append('<p class="bullet">• %s</p>' % html_lib.escape(line[4:]))
        elif line.startswith("- "):
            body.append('<p class="kv">%s</p>' % html_lib.escape(line[2:]))
        elif line.startswith("### "):
            body.append("<h3>%s</h3>" % html_lib.escape(line[4:]))
        elif line.startswith("**"):
            body.append('<p class="item-head">%s</p>' % line.replace("**", ""))
        else:
            body.append("<p>%s</p>" % line)
    body.append("</div>")
    css = """
@page { size: A4; margin: 1.8cm 2cm; }
body { font-family: "PingFang SC", "Noto Sans CJK SC", "Helvetica Neue", Arial, sans-serif;
       color: #1a1a1a; font-size: 10.5pt; line-height: 1.5; margin: 0; }
.page { max-width: 21cm; margin: 0 auto; }
h1 { font-size: 20pt; margin: 0 0 2pt; }
.headline { font-size: 11pt; color: #444; margin: 0 0 4pt; }
.contacts { font-size: 9.5pt; color: #555; margin: 0 0 10pt; }
h2 { font-size: 11.5pt; color: %s; border-bottom: 1.2pt solid %s;
     padding-bottom: 2pt; margin: 12pt 0 6pt; }
h3 { font-size: 10.5pt; margin: 8pt 0 2pt; }
p { margin: 0 0 4pt; }
.item-head { font-weight: 600; margin: 7pt 0 2pt; }
.bullet { margin: 0 0 2pt 10pt; }
.kv { margin: 0 0 2pt; }
""" % (accent, accent)
    return ("<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
            "<title>简历</title><style>%s</style></head><body>%s</body></html>"
            % (css, "\n".join(body)))


# ---------- 入口 ----------

def main():
    ap = argparse.ArgumentParser(description="reactive-resume 数据工具")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("validate", "ats"):
        p = sub.add_parser(name)
        p.add_argument("file")
    p = sub.add_parser("render")
    p.add_argument("file")
    p.add_argument("--format", choices=["md", "html"], default="md")
    p.add_argument("--out", default=None)
    args = ap.parse_args()

    path = Path(args.file)
    data, err = load_json(path)
    if err:
        print(err)
        return 1
    kind = detect(data)
    if kind == "unknown":
        print("无法识别文件类型：既不像 resume.json（无 基本信息/区块）也不像 career.json（无 投递/职业档案）")
        return 1

    if args.cmd == "validate":
        if kind == "resume":
            errors, warnings = validate_resume(data)
            return report("校验 resume: %s" % path, errors, warnings)
        errors, warnings = validate_career(data)
        return report("校验 career: %s" % path, errors, warnings)

    if args.cmd == "ats":
        if kind != "resume":
            print("ATS 扫描仅支持 resume.json")
            return 1
        issues = ats_scan(data)
        print("=" * 56)
        print("ATS 扫描: %s" % path)
        print("=" * 56)
        for i in issues:
            print("  - %s" % i)
        bad = [i for i in issues if not i.startswith("篇幅预估")]
        print("-" * 56)
        print("  %d 项待处理，%d 项正常" % (len(bad), len(issues) - len(bad)))
        return 0

    if args.cmd == "render":
        if kind != "resume":
            print("渲染仅支持 resume.json")
            return 1
        out = render_html(data) if args.format == "html" else render_md(data)
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(out, encoding="utf-8")
            print("已写出: %s" % args.out)
        else:
            sys.stdout.write(out)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
