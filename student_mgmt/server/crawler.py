# server/crawler.py
import random
import time
import requests
from bs4 import BeautifulSoup
from .models import get_conn

# ============================================================
# 学生数据爬取（示例）
# ============================================================

def crawl_dummy_students():
    """
    示例：从一个公开网页抓一些名字（你可以换成学校新闻等），
    然后生成假学生写入数据库。
    """
    url = "https://www.renmingmingzi.com/100gehaotingdexingming.html"  # 只是个示例网站
    try:
        resp = requests.get(url, timeout=5)
        resp.encoding = resp.apparent_encoding
    except Exception as e:
        print("⚠ 爬取失败：", e)
        return 0

    soup = BeautifulSoup(resp.text, "html.parser")
    names = [tag.get_text(strip=True) for tag in soup.find_all("p")][:30]
    majors = ["计算机", "人工智能", "通信工程", "软件工程"]
    classes = ["1班", "2班", "3班"]

    added = 0
    with get_conn() as conn:
        cur = conn.cursor()
        for i, name in enumerate(names):
            sno = f"2024{200+i:03d}"
            gender = random.choice(["男", "女"])
            major = random.choice(majors)
            class_name = major + random.choice(classes)
            try:
                # 注意：create_table.sql 中 students 表没有 student_no 字段
                # 使用 name, gender, major, class_name 等字段
                cur.execute("""
                INSERT INTO students (name, gender, major, class_name)
                VALUES (%s, %s, %s, %s)
                """, (name, gender, major, class_name))
                added += 1
            except Exception:
                conn.rollback()
    print(f"✅ 爬虫导入学生 {added} 条")
    return added

# ============================================================
# 北邮计算机学院教师爬取
# ============================================================

BUPT_SCS_URL = "https://scs.bupt.edu.cn/szjs1/jsyl.htm"


def fetch_page(url, timeout=10):
    """
    获取网页内容
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.encoding = "utf-8"
        return resp.text
    except Exception as e:
        print(f"⚠ 获取网页失败：{e}")
        raise


def parse_teacher_links(html):
    """
    从索引页面解析教师链接
    返回教师链接列表，每个链接包含 (姓名, URL)
    """
    import re
    
    try:
        soup = BeautifulSoup(html, "lxml")
    except:
        soup = BeautifulSoup(html, "html.parser")
    
    teacher_links = []
    
    # 方法1: 查找所有 teacher_table 表格中的链接
    teacher_tables = soup.find_all("table", class_="teacher_table")
    
    for table in teacher_tables:
        # 查找表格中所有的链接
        links = table.find_all("a", href=True)
        for link in links:
            href = link.get("href", "")
            text = link.get_text(strip=True)
            title = link.get("title", "")
            
            # 使用title属性或文本作为姓名
            name = title if title else text
            
            # 跳过空链接
            if not name or len(name) < 2:
                continue
            
            # 跳过明显不是教师姓名的
            if name in ["更多", "查看", "详情", "返回", "首页", "上一页", "下一页", "　"]:
                continue
            
            # 检查是否是中文姓名（2-4个中文字符）
            name_pattern = re.compile(r'^[\u4e00-\u9fa5]{2,4}$')
            if name_pattern.match(name):
                # 构建完整URL
                if href.startswith("http"):
                    full_url = href
                elif href.startswith("/"):
                    full_url = "https://scs.bupt.edu.cn" + href
                elif href.startswith("../"):
                    # 相对路径，需要根据当前页面URL构建
                    full_url = "https://scs.bupt.edu.cn/" + href.replace("../", "")
                elif href.startswith("#"):
                    # 跳过锚点链接
                    continue
                else:
                    # 其他相对路径
                    base_url = BUPT_SCS_URL.rsplit("/", 1)[0] + "/"
                    full_url = base_url + href
                
                teacher_links.append((name, full_url))
    
    # 如果表格方法没找到，尝试通用方法
    if not teacher_links:
        print("⚠ 未在teacher_table中找到链接，尝试通用方法...")
        all_links = soup.find_all("a", href=True)
        
        for link in all_links:
            href = link.get("href", "")
            text = link.get_text(strip=True)
            title = link.get("title", "")
            
            name = title if title else text
            
            if not name or len(name) < 2:
                continue
            if name in ["更多", "查看", "详情", "返回", "首页", "上一页", "下一页"]:
                continue
            if href.startswith("#") or href.startswith("javascript:"):
                continue
            
            # 检查文本是否是中文姓名
            name_pattern = re.compile(r'^[\u4e00-\u9fa5]{2,4}$')
            if name_pattern.match(name):
                if href.startswith("http"):
                    full_url = href
                elif href.startswith("/"):
                    full_url = "https://scs.bupt.edu.cn" + href
                else:
                    base_url = BUPT_SCS_URL.rsplit("/", 1)[0] + "/"
                    full_url = base_url + href
                
                teacher_links.append((name, full_url))
    
    # 去重（按姓名）
    seen_names = set()
    unique_links = []
    for name, url in teacher_links:
        if name not in seen_names:
            seen_names.add(name)
            unique_links.append((name, url))
    
    print(f"✅ 从索引页面找到 {len(unique_links)} 个教师链接")
    return unique_links


def parse_teacher_detail(html, default_name=""):
    """
    从教师详情页面解析教师信息
    """
    import re
    
    try:
        soup = BeautifulSoup(html, "lxml")
    except:
        soup = BeautifulSoup(html, "html.parser")
    
    teacher = {
        "name": default_name,
        "title": "",
        "department": "",
        "research": "",
        "email": "",
        "homepage": ""
    }
    
    # 获取页面所有文本
    page_text = soup.get_text()
    
    # 提取姓名（如果页面中有）
    if not teacher["name"]:
        name_pattern = re.compile(r'[\u4e00-\u9fa5]{2,4}')
        name_match = name_pattern.search(page_text[:500])  # 在前500字符中查找
        if name_match:
            teacher["name"] = name_match.group(0)
    
    # 提取职称
    title_keywords = ["教授", "副教授", "讲师", "助理教授", "研究员", "副研究员", "高级工程师"]
    for keyword in title_keywords:
        if keyword in page_text:
            teacher["title"] = keyword
            break
    
    # 提取系别/部门
    dept_keywords = ["系", "学院", "研究所", "中心"]
    for keyword in dept_keywords:
        dept_match = re.search(r'[\u4e00-\u9fa5]+' + keyword, page_text)
        if dept_match:
            teacher["department"] = dept_match.group(0)
            break
    
    # 提取邮箱
    email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    email_match = email_pattern.search(page_text)
    if email_match:
        teacher["email"] = email_match.group(0)
    
    # 尝试通过选择器查找结构化信息
    # 常见的标签模式
    info_selectors = {
        "name": ["h1", "h2", ".name", "[class*='name']"],
        "title": [".title", "[class*='title']", ".zc", "[class*='zc']"],
        "department": [".dept", "[class*='dept']", ".xy", "[class*='xy']"],
        "research": [".research", "[class*='research']", ".fx", "[class*='fx']"],
        "email": [".email", "[class*='email']", "a[href^='mailto:']"]
    }
    
    for key, selectors in info_selectors.items():
        if teacher[key]:  # 如果已经找到，跳过
            continue
        for selector in selectors:
            tag = soup.select_one(selector)
            if tag:
                if key == "email" and tag.name == "a":
                    href = tag.get("href", "")
                    if href.startswith("mailto:"):
                        teacher["email"] = href.replace("mailto:", "").strip()
                else:
                    text = tag.get_text(strip=True)
                    if text and len(text) < 100:  # 避免获取大段文本
                        teacher[key] = text
                break
    
    return teacher


def parse_teachers(html):
    """
    解析教师信息（兼容索引页和详情页）
    如果是索引页，返回链接列表；如果是详情页，返回教师信息
    """
    # 这个方法现在主要用于索引页，返回链接
    return parse_teacher_links(html)


def clean_teacher_data(teacher):
    """
    数据清洗：清理和规范化教师数据
    """
    # 清理姓名：去除多余空格
    teacher["name"] = " ".join(teacher["name"].split())
    
    # 规范化职称
    title = teacher["title"]
    if title:
        # 统一职称格式
        title_mapping = {
            "教授": "教授",
            "副教授": "副教授",
            "讲师": "讲师",
            "助理教授": "助理教授",
            "研究员": "研究员",
            "副研究员": "副研究员",
        }
        for key, value in title_mapping.items():
            if key in title:
                teacher["title"] = value
                break
    
    # 清理邮箱：验证格式
    email = teacher["email"]
    if email and "@" not in email:
        teacher["email"] = ""
    
    # 清理系别：统一格式
    dept = teacher["department"]
    if dept:
        # 去除"系"字后的多余内容，统一为"XX系"
        if "系" in dept:
            dept = dept.split("系")[0] + "系"
        teacher["department"] = dept
    
    return teacher


def crawl_bupt_scs_teachers(max_teachers=None, delay=1):
    """
    爬取北京邮电大学计算机学院教师名录并存储到数据库
    参数:
        max_teachers: 最大爬取数量（None表示全部）
        delay: 访问每个教师主页的延迟（秒），避免请求过快
    返回：(成功数量, 跳过数量, 错误信息)
    """
    print("开始爬取北京邮电大学计算机学院教师名录…")
    
    try:
        # 第一步：获取索引页面，提取教师链接
        print("📋 步骤1: 获取教师列表索引页...")
        html = fetch_page(BUPT_SCS_URL)
        teacher_links = parse_teacher_links(html)
        
        if not teacher_links:
            return 0, 0, "未找到教师链接，请检查网页结构是否变化"
        
        print(f"✅ 找到 {len(teacher_links)} 个教师链接")
        
        # 限制数量（用于测试）
        if max_teachers:
            teacher_links = teacher_links[:max_teachers]
            print(f"⚠ 限制爬取数量为 {max_teachers}")
        
        # 第二步：访问每个教师主页，获取详细信息
        print(f"📋 步骤2: 开始访问教师主页（共 {len(teacher_links)} 个）...")
        
        added = 0
        skipped = 0
        errors = []
        
        with get_conn() as conn:
            cur = conn.cursor()
            
            for idx, (name, url) in enumerate(teacher_links, 1):
                try:
                    print(f"  [{idx}/{len(teacher_links)}] 正在处理: {name}...", end=" ")
                    
                    # 检查是否已存在
                    cur.execute("SELECT teacher_id FROM teachers WHERE name = %s", (name,))
                    if cur.fetchone():
                        print("已存在，跳过")
                        skipped += 1
                        continue
                    
                    # 访问教师主页
                    try:
                        detail_html = fetch_page(url)
                        teacher = parse_teacher_detail(detail_html, default_name=name)
                    except Exception as e:
                        print(f"访问失败: {e}")
                        # 即使访问失败，也尝试用索引页的姓名创建基本记录
                        teacher = {
                            "name": name,
                            "title": "",
                            "department": "计算机学院",
                            "research": "",
                            "email": "",
                            "homepage": url
                        }
                    
                    # 数据清洗
                    teacher = clean_teacher_data(teacher)
                    
                    if not teacher["name"]:
                        print("姓名无效，跳过")
                        skipped += 1
                        continue
                    
                    # 插入数据库
                    # 注意：create_table.sql 中 teachers 表字段为 department 而不是 dept
                    cur.execute("""
                        INSERT INTO teachers (name, department, title, email, research)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        teacher["name"],
                        teacher["department"] or "计算机学院",
                        teacher["title"],
                        teacher["email"],
                        teacher.get("research", "")
                    ))
                    print("✅ 成功")
                    added += 1
                    
                    # 延迟，避免请求过快
                    if delay > 0 and idx < len(teacher_links):
                        time.sleep(delay)
                    
                except Exception as e:
                    error_msg = f"处理教师 {name} 时出错：{str(e)}"
                    errors.append(error_msg)
                    print(f"❌ 失败: {e}")
                    continue
        
        result_msg = f"✅ 完成！成功导入 {added} 名教师，跳过 {skipped} 条重复数据"
        if errors:
            result_msg += f"，{len(errors)} 条错误"
        print(result_msg)
        
        return added, skipped, "; ".join(errors) if errors else None
        
    except Exception as e:
        error_msg = f"爬取失败：{str(e)}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        return 0, 0, error_msg


def debug_page_structure(url=BUPT_SCS_URL):
    """
    调试函数：获取并保存网页内容，分析结构
    """
    print("=" * 60)
    print("调试模式：分析网页结构")
    print("=" * 60)
    
    try:
        html = fetch_page(url)
        
        # 保存原始HTML到文件
        with open("bupt_page_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("✅ 网页内容已保存到 bupt_page_debug.html")
        
        # 解析并分析
        soup = BeautifulSoup(html, "html.parser")
        
        print(f"\n页面标题: {soup.title.string if soup.title else '无'}")
        print(f"页面总字符数: {len(html)}")
        
        # 查找所有可能的容器
        print("\n查找可能的教师容器...")
        containers = [
            ("div.teacher_li", soup.select("div.teacher_li")),
            ("div[class*='teacher']", soup.select("div[class*='teacher']")),
            ("li[class*='teacher']", soup.select("li[class*='teacher']")),
            ("table tr", soup.select("table tr")),
            ("div.list-item", soup.select("div.list-item")),
            ("ul li", soup.select("ul li")[:20]),  # 限制数量
        ]
        
        for selector, items in containers:
            if items:
                print(f"  ✅ {selector}: 找到 {len(items)} 个")
                # 打印第一个元素的结构
                if len(items) > 0:
                    first = items[0]
                    print(f"     第一个元素: {first.name}, class={first.get('class')}")
                    print(f"     文本预览: {first.get_text(strip=True)[:100]}")
            else:
                print(f"  ❌ {selector}: 未找到")
        
        # 查找所有包含中文姓名的元素
        import re
        name_pattern = re.compile(r'[\u4e00-\u9fa5]{2,4}')
        potential_names = []
        for tag in soup.find_all(["div", "li", "td", "span", "p"]):
            text = tag.get_text(strip=True)
            if name_pattern.match(text) and 2 <= len(text) <= 4:
                if text not in ["姓名", "职称", "系别", "邮箱", "研究方向", "更多", "查看"]:
                    potential_names.append((tag.name, tag.get("class"), text))
        
        if potential_names:
            print(f"\n找到 {len(potential_names)} 个可能的姓名:")
            for tag_name, classes, name in potential_names[:20]:
                print(f"  {tag_name} (class={classes}): {name}")
        
        return html
        
    except Exception as e:
        print(f"❌ 调试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "debug":
        # 调试模式
        debug_page_structure()
    else:
        # 正常爬虫模式
        added, skipped, error = crawl_bupt_scs_teachers()
        print(f"结果：成功 {added}，跳过 {skipped}，错误：{error or '无'}")
