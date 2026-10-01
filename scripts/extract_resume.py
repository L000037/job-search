# -*- coding: utf-8 -*-
"""
简历文本抽取：支持 .docx（零依赖）与 .pdf（需 pypdf，可选 PyPDF2 回退）。
用法：
    python extract_resume.py "<简历路径>"
    python extract_resume.py --selftest
成功时把全文打印到 stdout（UTF-8），供调用方读取；失败时非零退出并打印原因。
"""
import os
import re
import sys
import zipfile


def extract_docx(path: str) -> str:
    """docx 即 zip；word/document.xml 内含正文与表格文字，无需第三方库。"""
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
    # 段落与表格行结尾转换行，制表符转换
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab[^>]*/>", "\t", xml)
    xml = re.sub(r"<w:br[^>]*/>", "\n", xml)
    # 去掉所有剩余标签
    text = re.sub(r"<[^>]+>", "", xml)
    # XML 实体
    text = (text.replace("&amp;", "&").replace("&lt;", "<")
                .replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'"))
    lines = [ln.strip() for ln in text.splitlines()]
    out, blank = [], False
    for ln in lines:
        if ln:
            out.append(ln)
            blank = False
        elif not blank:
            out.append("")
            blank = True
    return "\n".join(out).strip()


def extract_pdf(path: str) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except ImportError:
            print("ERROR: 解析 PDF 需要 pypdf，请先运行：pip install pypdf", file=sys.stderr)
            sys.exit(2)
    reader = PdfReader(path)
    parts = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(p for p in parts if p).strip()


def extract(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        text = extract_docx(path)
    elif ext == ".pdf":
        text = extract_pdf(path)
    elif ext == ".doc":
        print("ERROR: 不支持旧版 .doc，请用 Word 另存为 .docx 或 .pdf 后重试", file=sys.stderr)
        sys.exit(2)
    else:
        print(f"ERROR: 不支持的文件类型 {ext}（仅支持 .docx/.pdf）", file=sys.stderr)
        sys.exit(2)
    if not text:
        print("ERROR: 未抽取到任何文字（可能是扫描件/图片版 PDF），请提供可复制文字的版本", file=sys.stderr)
        sys.exit(1)
    return text


def selftest() -> None:
    """在临时目录构造一个最小 docx 并验证抽取逻辑。"""
    import tempfile

    content_types = (
        '<?xml version="1.0"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>'
    )
    document = (
        '<?xml version="1.0"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        "<w:p><w:r><w:t>张三  产品经理</w:t></w:r></w:p>"
        "<w:p><w:r><w:t>2027届本科 计算机科学</w:t></w:r></w:p>"
        "</w:body></w:document>"
    )
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "demo.docx")
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", content_types)
            z.writestr("_rels/.rels", rels)
            z.writestr("word/document.xml", document)
        text = extract_docx(p)
    assert "张三" in text and "2027届本科" in text, text
    print("selftest ok:\n" + text)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python extract_resume.py <简历.docx|简历.pdf> | --selftest", file=sys.stderr)
        sys.exit(2)
    if sys.argv[1] == "--selftest":
        selftest()
    else:
        print(extract(sys.argv[1]))
