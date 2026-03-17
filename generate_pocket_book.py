# -*- coding: utf-8 -*-
"""
口袋单词本生成器
从「三张表.pdf」提取单词数据，生成可打印的A4口袋书PDF。
打印后裁剪即成 5cm × 7cm 的口袋单词卡。

使用方法：python generate_pocket_book.py
"""
import re
import sys
import os
import argparse
from datetime import datetime
import fitz
from fpdf import FPDF

# ============================================================
# 配置
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def get_smart_color(text):
    """根据文本内容智能选择颜色"""
    text = text.strip()
    # 编号（纯数字）
    if re.match(r'^\d+$', text):
        return '#dc2d1e'  # 红色
    # 包含中文
    if re.search(r'[\u4e00-\u9fff]', text):
        return '#000000'  # 黑色
    # 纯英文/标点
    return '#1e5a8c'  # 深蓝色
DEFAULT_INPUT_PDF = os.path.join(SCRIPT_DIR, "三张表.pdf")

def get_output_filename(base_name: str, output_dir: str = None) -> str:
    """生成结合 日期和编号 的动态文件名"""
    out_dir = output_dir if output_dir else SCRIPT_DIR
    today_str = datetime.now().strftime("%Y%m%d")
    idx = 1
    while True:
        filename = f"{base_name}_{today_str}_{idx:02d}.pdf"
        output_path = os.path.join(out_dir, filename)
        if not os.path.exists(output_path):
            return output_path
        idx += 1

# 口袋书卡片尺寸（毫米）
CARD_W = 50  # 5cm
CARD_H = 70  # 7cm

# A4横向尺寸（毫米）
A4_W = 297
A4_H = 210

# 网格布局：4列 × 2行 = 每面8格
COLS = 4
ROWS = 2

# 每本小册子页面数（1张纸正反面 = 16页）
PAGES_PER_BOOKLET = 16
CONTENT_PAGES = 14  # 去掉封面和封底 = 14个单词

# 骑马钉拼版布局 (Saddle Stitch Imposition)
# 我们将这16面排版为4个10x7cm的纸条。
# 用户打印后切成4个纸条，对折后嵌套在一起即可成为完美连续小册子！
FRONT_MAP = [
    15,  0, 13,  2, 
    11,  4,  9,  6
]
BACK_MAP = [
     1, 14,  3, 12, 
     5, 10,  7,  8
]

# 字体路径（Windows 微软雅黑）
FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"

def parse_entries(pdf_path: str) -> list[dict]:
    """
    解析PDF文本并保留源颜色结构，返回条目列表。
    每个条目包含 HTML 渲染文本供fpdf的 write_html() 使用。
    """
    doc = fitz.open(pdf_path)
    entries = []
    current_entry = None
    expected_number = None  # 自动检测起始序号

    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]

        for b in blocks:
            if "lines" not in b:
                continue

            block_text = "".join(span['text'] for line in b["lines"] for span in line["spans"]).strip()
            if not block_text:
                continue

            # 跳过页眉页脚或干扰元素
            if re.match(r'^\d+-\d+$', block_text) or block_text == str(page_num + 1) or "扫描全能王" in block_text:
                continue

            # 去除行首的●符号后再匹配序号
            cleaned_text = re.sub(r'^[●·•]\s*', '', block_text)

            # 检查block中间是否包含"◆◆数字"或"●数字"模式（处理多条目合并的情况）
            mid_match = re.search(r'[◆●·•]{1,2}(\d{1,4})\s+', cleaned_text)
            if mid_match and expected_number is not None:
                mid_number = int(mid_match.group(1))
                if mid_number == expected_number:
                    # 找到了期望的编号在block中间，需要分割block
                    split_pos = mid_match.start()

                    # 只提取编号之前的文本归入前一个条目
                    if current_entry and split_pos > 0:
                        before_text = cleaned_text[:split_pos].strip()
                        if before_text:
                            before_block = {
                                'lines': [{
                                    'spans': [{
                                        'text': before_text,
                                        'size': 12,
                                        'color': 0xdc2d1e
                                    }]
                                }]
                            }
                            current_entry['blocks'].append(before_block)

                    # 提取编号及之后的文本创建新条目
                    after_text = cleaned_text[split_pos:].strip()
                    # 移除开头的符号，保留"397 ［谚］..."格式
                    after_text = re.sub(r'^[◆●·•]{1,2}', '', after_text)
                    if after_text.strip():
                        new_block = {
                            'lines': [{
                                'spans': [{
                                    'text': after_text,
                                    'size': 12,
                                    'color': 0xdc2d1e
                                }]
                            }]
                        }
                        current_entry = {'number': mid_number, 'blocks': [new_block]}
                    else:
                        current_entry = {'number': mid_number, 'blocks': []}

                    entries.append(current_entry)
                    expected_number += 1
                    continue

            # 优先尝试精确匹配期望的序号（解决序号与后续数字粘连的问题，如"1851945年"应匹配185）
            matched_number = None
            if expected_number is not None:
                prefix = str(expected_number)
                if cleaned_text.startswith(prefix):
                    rest = cleaned_text[len(prefix):]
                    if rest and not rest[0].isdigit():  # 序号后面不能紧跟数字（避免误匹配）
                        matched_number = expected_number
                    elif rest and rest[0].isdigit():
                        # 可能是粘连情况，检查去掉期望序号后剩余部分是否以非字母数字开头
                        # 例如 "1851945年" -> 期望185, rest="1945年", "1945年"首字符是数字
                        # 但rest去掉数字后如果有中文则说明确实是粘连
                        rest_after_digits = re.sub(r'^\d+', '', rest)
                        if rest_after_digits and re.match(r'[^\da-zA-Z\.\-]', rest_after_digits):
                            matched_number = expected_number
            # 如果精确匹配失败，使用通用正则
            if matched_number is None:
                m = re.match(r'^(\d{1,4})\s*([^\da-zA-Z\.\-].*)', cleaned_text)
                if m:
                    matched_number = int(m.group(1))
            if matched_number is not None:
                # 自动检测起始序号：首次匹配到的数字即为起始
                if expected_number is None:
                    expected_number = matched_number
                if matched_number == expected_number:
                    current_entry = {'number': matched_number, 'blocks': [b]}
                    entries.append(current_entry)
                    expected_number += 1
                    continue
                elif matched_number > expected_number:
                    # 跳过了某些编号，继续解析
                    current_entry = {'number': matched_number, 'blocks': [b]}
                    entries.append(current_entry)
                    expected_number = matched_number + 1
                    continue

            if current_entry:
                current_entry['blocks'].append(b)
                
    # 转换为HTML排版格式
    for entry in entries:
        html = []
        blocks = entry['blocks']

        # 检测第一个block是否只包含序号数字，若是则与下一个block合并作为标题
        first_text = "".join(
            span['text'] for line in blocks[0]['lines'] for span in line['spans']
        ).strip()
        # 去除可能的●前缀再判断
        first_text_clean = re.sub(r'^[●·•]\s*', '', first_text)
        title_end_idx = 0  # 标题包含到哪个block索引（含）
        if re.match(r'^\d{1,4}$', first_text_clean) and len(blocks) > 1:
            title_end_idx = 1  # 合并前两个block
        
        # 构建标题HTML（去除所有空格使数字与文字连为一体，防止fpdf2在空格处换行）
        title_spans = []
        is_first_span = True
        for bi in range(title_end_idx + 1):
            b = blocks[bi]
            for line in b['lines']:
                line_htmls = []
                for span in line['spans']:
                    text = span['text'].replace('<', '&lt;').replace('>', '&gt;')
                    # 去除所有空格，确保"84 "→"84"、"84 ""→"84""
                    text = text.replace(' ', '')
                    # 去除标题中的●·•前缀符号
                    if is_first_span:
                        text = re.sub(r'^[●·•]+\s*', '', text)
                        is_first_span = False
                    color_hex = get_smart_color(text)
                    if not text:
                        continue
                    line_htmls.append(f'<font color="{color_hex}">{text}</font>')
                if line_htmls:
                    title_spans.append("".join(line_htmls))
        title_html = "".join(title_spans)
        html.append(f'<font size="10"><b>{title_html}</b></font><br>')
        
        # 剩余block作为条目
        for b_idx in range(title_end_idx + 1, len(blocks)):
            b = blocks[b_idx]
            span_htmls = []
            text_raw = ""
            is_first_span_in_block = True
            for line in b['lines']:
                line_span_htmls = []
                for span in line['spans']:
                    text = span['text'].replace('<', '&lt;').replace('>', '&gt;')
                    # 去除内容行首的●·•前缀（PDF源文本自带的，代码会自己添加红色●）
                    if is_first_span_in_block:
                        text = re.sub(r'^[●·•]+\s*', '', text)
                        is_first_span_in_block = False
                    text_raw += span['text']
                    color_hex = get_smart_color(text)
                    if text.strip() == '':
                        line_span_htmls.append('&nbsp;')
                    else:
                        line_span_htmls.append(f'<font color="{color_hex}">{text}</font>')
                span_htmls.append("".join(line_span_htmls))
                text_raw += "\n"
            
            block_html = "<br>".join(span_htmls)
            
            # 判断是否为语法区块
            is_grammar = bool(re.search(r'(过去时|现在时|将来时|被动态|主动态|语法|注意|主句|从句)', text_raw))
            if is_grammar and re.search(r'[a-zA-Z]{5,}', text_raw): 
                is_grammar = False
            
            prefix_html = '<font color="#dc2d1e">●</font> '
            if is_grammar:
                prefix_html = '<font color="#999999">|</font> '
                
            html.append(f'<font size="9">{prefix_html}{block_html}</font><br>')
            
        entry['html'] = "".join(html)

    return entries


# ============================================================
# 步骤2：口袋书 PDF 生成
# ============================================================

class PocketBookPDF(FPDF):
    """口袋书PDF生成器"""

    def __init__(self):
        super().__init__(orientation='L', unit='mm', format='A4')
        self.set_auto_page_break(auto=False)
        # 注册中文字体及后备字体（应对音标显示）
        self.add_font('msyh', '', FONT_PATH)
        self.add_font('msyh', 'B', r"C:\Windows\Fonts\msyhbd.ttc")
        try:
            self.add_font('arial', '', r'C:\Windows\Fonts\arial.ttf')
            self.add_font('segoe', '', r'C:\Windows\Fonts\segoeui.ttf')
            self.set_fallback_fonts(['segoe', 'arial'])
        except Exception:
            pass
        
        # 创建用于测量HTML高度的临时PDF（避免内容溢出卡片边界）
        self._temp_pdf = FPDF(orientation='L', unit='mm', format='A4')
        self._temp_pdf.set_auto_page_break(auto=False)
        self._temp_pdf.add_font('msyh', '', FONT_PATH)
        self._temp_pdf.add_font('msyh', 'B', r"C:\Windows\Fonts\msyhbd.ttc")
        try:
            self._temp_pdf.add_font('arial', '', r'C:\Windows\Fonts\arial.ttf')
            self._temp_pdf.add_font('segoe', '', r'C:\Windows\Fonts\segoeui.ttf')
            self._temp_pdf.set_fallback_fonts(['segoe', 'arial'])
        except Exception:
            pass

    def _calc_grid_origin(self) -> tuple[float, float]:
        """计算网格左上角原点（居中放置）"""
        total_w = COLS * CARD_W
        total_h = ROWS * CARD_H
        x0 = (A4_W - total_w) / 2
        y0 = (A4_H - total_h) / 2
        return x0, y0

    def _get_card_rect(self, index: int) -> tuple[float, float, float, float]:
        """
        根据卡片索引(0~7)获取在页面上的矩形坐标。
        返回 (x, y, w, h)
        """
        x0, y0 = self._calc_grid_origin()
        col = index % COLS
        row = index // COLS
        x = x0 + col * CARD_W
        y = y0 + row * CARD_H
        return x, y, CARD_W, CARD_H

    def draw_cut_marks(self):
        """绘制裁剪标记线"""
        x0, y0 = self._calc_grid_origin()
        self.set_draw_color(180, 180, 180)
        self.set_line_width(0.2)

        # 竖线
        for i in range(COLS + 1):
            x = x0 + i * CARD_W
            # 上方短线
            self.line(x, y0 - 5, x, y0)
            # 中间线（两行之间）
            # 下方短线
            self.line(x, y0 + ROWS * CARD_H, x, y0 + ROWS * CARD_H + 5)

        # 横线
        for j in range(ROWS + 1):
            y = y0 + j * CARD_H
            self.line(x0 - 5, y, x0, y)
            self.line(x0 + COLS * CARD_W, y, x0 + COLS * CARD_W + 5, y)

        # 绘制完整网格线（虚线效果用浅灰色实线代替）
        self.set_draw_color(220, 220, 220)
        self.set_line_width(0.1)
        for i in range(COLS + 1):
            x = x0 + i * CARD_W
            self.line(x, y0, x, y0 + ROWS * CARD_H)
        for j in range(ROWS + 1):
            y = y0 + j * CARD_H
            self.line(x0, y, x0 + COLS * CARD_W, y)

    def draw_cover(self, card_index: int, start_num: int, end_num: int, booklet_index: int):
        """绘制封面卡片"""
        x, y, w, h = self._get_card_rect(card_index)
        padding = 3

        # 背景色
        self.set_fill_color(70, 130, 180)  # Steel Blue
        self.rect(x + 0.5, y + 0.5, w - 1, h - 1, 'F')

        # 标题
        self.set_font('msyh', 'B', 11)
        self.set_text_color(255, 255, 255)
        title = "口袋单词本"
        tw = self.get_string_width(title)
        self.text(x + (w - tw) / 2, y + h * 0.35, title)

        # 编号范围
        self.set_font('msyh', 'B', 14)
        range_text = f"{start_num}~{end_num}"
        rw = self.get_string_width(range_text)
        self.text(x + (w - rw) / 2, y + h * 0.55, range_text)

        # 册号
        self.set_font('msyh', '', 7)
        vol_text = f"第{booklet_index}册"
        vw = self.get_string_width(vol_text)
        self.text(x + (w - vw) / 2, y + h * 0.75, vol_text)

        # 重置颜色
        self.set_text_color(0, 0, 0)

    def draw_back_cover(self, card_index: int):
        """绘制封底卡片"""
        x, y, w, h = self._get_card_rect(card_index)

        # 淡灰背景
        self.set_fill_color(240, 240, 240)
        self.rect(x + 0.5, y + 0.5, w - 1, h - 1, 'F')

        self.set_font('msyh', '', 7)
        self.set_text_color(150, 150, 150)
        label = "口袋单词本"
        lw = self.get_string_width(label)
        self.text(x + (w - lw) / 2, y + h / 2, label)
        self.set_text_color(0, 0, 0)

    def _measure_html_height(self, html: str, inner_w: float, entry_num=None) -> float:
        """使用临时PDF测量HTML内容的渲染高度"""
        self._temp_pdf.add_page()
        temp_cx = 10
        start_y = 10
        self._temp_pdf.set_y(start_y)
        self._temp_pdf.set_left_margin(temp_cx)
        # 使用与实际卡片相同的宽度设置
        self._temp_pdf.set_right_margin(A4_W - temp_cx - inner_w)
        self._temp_pdf.set_x(temp_cx)
        self._temp_pdf.set_font('msyh', '', 9)
        try:
            self._temp_pdf.write_html(html)
            return self._temp_pdf.get_y() - start_y
        except Exception:
            # 渲染失败，返回-1表示无法测量
            return -1

    @staticmethod
    def _scale_html_fonts(html: str, scale: float) -> str:
        """按比例缩小HTML中的字体大小"""
        def replace_size(match):
            old_size = float(match.group(1))
            new_size = max(5, old_size * scale)
            return f'size="{new_size:.1f}"'
        return re.sub(r'size="(\d+\.?\d*)"', replace_size, html)

    def draw_word_card(self, card_index: int, entry: dict):
        """绘制单词内页卡片（自动缩放字体 + PDF裁剪区域防止溢出）"""
        x, y, w, h = self._get_card_rect(card_index)
        padding = 2
        inner_w = w - 2 * padding
        cx = x + padding
        cy = y + padding
        max_h = h - 2 * padding

        html = entry['html']
        entry_num = entry.get('number', '?')

        # 自动缩放字体：内容过多则缩小，内容过少则放大
        # 目标：让内容高度尽量接近卡片高度的 95%（充分利用空间）
        measured_h = self._measure_html_height(html, inner_w, entry_num)
        target_fill = max_h * 0.95  # 目标填充 95%

        if measured_h < 0:
            # 测量失败，使用保守估算值（假设占50%高度），然后尝试放大
            measured_h = max_h * 0.5

        if measured_h > max_h:
            # 内容溢出，缩小字体（最小缩放到65%）
            scale = max(0.65, max_h / measured_h * 0.95)
            html = self._scale_html_fonts(html, scale)
        elif measured_h < target_fill and measured_h > 0:
            # 内容不足目标的 95%，用二分法精确放大
            lo, hi = 1.0, 3.5  # 最多放大3.5倍
            best_html = html
            best_scale = 1.0
            failed_count = 0
            for _ in range(10):  # 10轮二分更精确
                mid = (lo + hi) / 2
                trial_html = self._scale_html_fonts(entry['html'], mid)
                trial_h = self._measure_html_height(trial_html, inner_w, entry_num)
                if trial_h < 0:
                    # 测量失败，说明这个缩放太大了
                    hi = mid
                    failed_count += 1
                elif trial_h <= max_h * 0.98:  # 允许填充到98%
                    best_html = trial_html
                    best_scale = mid
                    lo = mid  # 还能更大
                else:
                    hi = mid  # 太大了
            html = best_html
            final_h = self._measure_html_height(html, inner_w, entry_num) if failed_count == 0 else measured_h * best_scale
        else:
            pass

        # 使用PDF裁剪区域防止内容溢出到相邻卡片
        self._out('q')  # 保存图形状态
        self._out(
            f'{x * self.k:.2f} {(self.h - y) * self.k:.2f} '
            f'{w * self.k:.2f} {-h * self.k:.2f} re W n'
        )

        self.set_y(cy)
        self.set_left_margin(cx)
        self.set_right_margin(A4_W - cx - inner_w)
        self.set_x(cx)
        try:
            self.write_html(html)
        except Exception:
            # 如果渲染失败，用纯文本回退
            self.set_font('msyh', '', 7)
            plain = re.sub('<[^<]+>', '', entry['html']).replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>')
            self.multi_cell(w=inner_w, h=3, text=plain[:200])
        
        self._out('Q')  # 恢复图形状态（移除裁剪）
        
        # 恢复默认边距
        self.set_left_margin(10)
        self.set_right_margin(10)


# ============================================================
# 步骤3：组装口袋书
# ============================================================

def generate_pocket_book(entries: list[dict], output_path: str):
    """
    将单词条目生成口袋书PDF。
    每本小册子：1封面 + 14 内页 + 1封底 = 16面
    每张A4纸正面8面（4列×2行），反面8面
    """
    pdf = PocketBookPDF()

    # 分组：每14个单词一本小册子
    booklets = []
    for i in range(0, len(entries), CONTENT_PAGES):
        booklets.append(entries[i:i + CONTENT_PAGES])

    print(f"共 {len(entries)} 个单词，分为 {len(booklets)} 本小册子")

    for bi, booklet_entries in enumerate(booklets):
        start_num = booklet_entries[0]['number']
        end_num = booklet_entries[-1]['number']
        print(f"  第{bi+1}册: {start_num}~{end_num} ({len(booklet_entries)}个单词)")

        # 构建16面内容列表
        # pages[0] = 封面, pages[1~14] = 单词, pages[15] = 封底
        pages = ['cover'] + list(range(len(booklet_entries))) + ['back']
        # 补齐到16面
        while len(pages) < PAGES_PER_BOOKLET:
            pages.insert(1, 'blank')

        # === 正面（A4第1页） ===
        pdf.add_page()
        pdf.draw_cut_marks()

        for idx, logical_page in enumerate(FRONT_MAP):
            page_content = pages[logical_page]
            if page_content == 'cover':
                pdf.draw_cover(idx, start_num, end_num, bi + 1)
            elif page_content == 'back':
                pdf.draw_back_cover(idx)
            elif page_content == 'blank':
                pass
            else:
                pdf.draw_word_card(idx, booklet_entries[page_content])

        # === 反面（A4第2页） ===
        pdf.add_page()
        pdf.draw_cut_marks()

        for idx, logical_page in enumerate(BACK_MAP):
            page_content = pages[logical_page]
            if page_content == 'cover':
                pdf.draw_cover(idx, start_num, end_num, bi + 1)
            elif page_content == 'back':
                pdf.draw_back_cover(idx)
            elif page_content == 'blank':
                pass
            else:
                pdf.draw_word_card(idx, booklet_entries[page_content])

    pdf.output(output_path)
    print(f"\n✅ 口袋单词本已生成: {output_path}")
    print(f"   共 {pdf.pages_count} 页A4纸（双面打印后裁剪）")


# ============================================================
# 主程序
# ============================================================

def main():
    sys.stdout.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(description="口袋单词本生成器")
    parser.add_argument("input", nargs="?", default=DEFAULT_INPUT_PDF, help="输入的PDF文件路径")
    parser.add_argument("-n", "--name", help="手动指定生成的自定义词书名称前缀")
    parser.add_argument("-o", "--output-dir", help="指定输出目录（默认为脚本所在目录）")
    args = parser.parse_args()

    input_pdf = os.path.abspath(args.input)
    if args.name:
        base_name = args.name
    else:
        # 默认使用封面标题作为文件名前缀
        base_name = "口袋单词本"

    output_dir = os.path.abspath(args.output_dir) if args.output_dir else None
    output_pdf = get_output_filename(base_name, output_dir)

    print("=" * 50)
    print("  口袋单词本自动排版印前引擎")
    print("=" * 50)

    # 1. 提取PDF文本并解析条目
    print(f"\n📖 正在读取并解析: {input_pdf}")
    if not os.path.exists(input_pdf):
        print(f"❌ 文件不存在: {input_pdf}")
        sys.exit(1)

    entries = parse_entries(input_pdf)
    print(f"   解析出 {len(entries)} 个单词条目")

    if not entries:
        print("❌ 未找到任何单词条目")
        sys.exit(1)

    # 打印前3个条目预览
    print("\n📋 前3个条目预览:")
    for e in entries[:3]:
        # preview text from html roughly
        preview = re.sub('<[^<]+>', '', e.get('html', ''))[:50].replace('\n', ' ')
        print(f"   #{e['number']}: {preview}...")

    # 3. 生成口袋书PDF
    print(f"\n🖨️  正在生成口袋书: {output_pdf}")
    generate_pocket_book(entries, output_pdf)

    print("\n✂️  使用说明:")
    print("   1. A4纸【双面打印，翻转短边】")
    print("   2. 剪掉四周白边，得到 20cm × 14cm 矩形")
    print("   3. 沿网格十字线剪开，得到 4 张 10cm × 7cm 的双面纸条")
    print("   4. 将每张纸条沿中间对折，按照封面图案嵌套在一起")
    print("   5. 左侧装订，完美16面小册子完成！")


if __name__ == '__main__':
    main()
