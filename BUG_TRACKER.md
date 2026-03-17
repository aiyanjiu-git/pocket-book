# Bug 追踪记录

## 🔴 活跃 Bug

---

## 🟢 已解决 Bug

### 功能改进 #4: 文字颜色单一问题

**报告时间**: 2026-03-15
**状态**: ✅ 已完成
**类型**: 功能改进

**问题描述**:
口袋书中文字颜色太单一，大部分仅为黑色，需要用不同颜色区分内容类型，突出重点，便于阅读。

**解决方案**:
添加智能着色功能，根据文本内容自动应用不同颜色：
- **编号**（纯数字）：红色 `#dc2d1e`
- **中文内容**：黑色 `#000000`
- **英文例句**：深蓝色 `#1e5a8c`

**修改内容**:
- 📄 文件: `generate_pocket_book.py:20-32, 209, 233`
- ✏️ 改动:
  ```python
  def get_smart_color(text):
      """根据文本内容智能选择颜色"""
      text = text.strip()
      if re.match(r'^\d+$', text):
          return '#dc2d1e'  # 红色 - 编号
      if re.search(r'[\u4e00-\u9fff]', text):
          return '#000000'  # 黑色 - 中文
      return '#1e5a8c'  # 深蓝色 - 英文
  ```

**验证结果**: ✅ 用户确认满足需求

**效果**:
- 编号醒目（红色）
- 中文释义清晰（黑色）
- 英文例句易区分（深蓝色）
- 提升阅读体验和重点识别

---

### Bug #3: 第396条内容混入第397条内容

**报告时间**: 2026-03-15
**状态**: ✅ 已解决
**严重程度**: 🔥 高

**问题描述**:
口袋单词本_20260315_04.pdf中，第396条内容混入了第397条的内容"397［谚］说比做容易。"

**根本原因**:
Bug #2第二次修复时，检测到mid-block编号（◆◆397）后，将**整个block**分配给前一个条目（396），导致包含"397［谚］说比做容易。"的完整内容都归入了396。

**最终解决方案**:
修改mid-block分割逻辑（generate_pocket_book.py:95-129），只提取编号之前的文本归入前一个条目：
```python
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
```

**修复效果**:
- 第396条：内容正确，不再混入397的内容
- 第397条：完整显示"397 ［谚］说比做容易。Easier said than done."
- 全部140个条目正确分配

---

## Bug #2: 部分单词遗漏 + 第354条字体太小

**报告时间**: 2026-03-14
**状态**: ✅ 已解决
**严重程度**: 🔥 高

### 问题描述
用户反馈口袋单词本_20260314_02.pdf（来源：三张表（351-490）.pdf）存在两个问题：
1. 部分单词本页面空白，遗漏了部分内容（如356、359等），在351~364范围内有多处遗漏
2. 第354条字体仍然太小，要求字体区域占总体三分之二以上

### 根本原因

**问题1：内容遗漏**
- 源PDF包含351-490（140个条目），但缺少397
- 原代码要求编号严格连续：`if matched_number == expected_number`
- 当遇到397缺失时，398被识别但不等于expected_number(397)，进入else分支
- 398及后续所有内容被当作396的附加内容，导致只解析出351-396（46个条目）
- 用户看到的"356、359遗漏"实际上是397之后的所有条目（398-490）都缺失

**问题2：第354条字体太小**
- 第354条的HTML在初始字体（10/9）下测量失败，返回-1
- 原代码遇到测量失败时直接跳过缩放：`if measured_h < 0: pass`
- 导致使用原始小字体（10/9）渲染，填充率接近0%

### 最终解决方案

#### 修改1：添加容错逻辑，允许跳过缺失编号
**文件**: `generate_pocket_book.py`
**位置**: `parse_entries`函数（约118行）
```python
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
```
**原因**: 允许编号不连续，遇到缺失编号时继续解析后续内容，而不是停止。

#### 修改2：测量失败时使用估算值
**文件**: `generate_pocket_book.py`
**位置**: `draw_word_card`方法（约405行）
```python
if measured_h < 0:
    # 测量失败，使用保守估算值（假设占50%高度），然后尝试放大
    measured_h = max_h * 0.5
```
**原因**: 测量失败时不放弃缩放，而是使用保守估算值，确保字体能被放大。

### 修复效果
- **内容遗漏**: 从46个条目提升到140个条目（351-490完整，包括397）
- **第354条**: 从0%填充（原始小字体）提升到90.7%填充（1.52倍放大）
- **编号分布**: 每册14个单词，无空白页
- **其他条目**: 所有测量失败的条目都能获得合理的字体放大

### 修复历史

#### 第一次修复（2026-03-14）
- 添加容错逻辑：`elif matched_number > expected_number`
- 测量失败时使用50%估算值
- 结果：解析出139个条目，跳过397

#### 第二次修复（2026-03-15）
- 添加block中间编号检测：`re.search(r'[◆●·•]{1,2}(\d{1,4})\s+', cleaned_text)`
- 处理397在block中间的特殊情况
- 结果：解析出140个条目，完整覆盖351-490

### 经验教训
1. **容错设计**: 解析逻辑应该容忍源数据的不完美（编号缺失、格式异常等）
2. **优雅降级**: 当精确测量失败时，使用估算值比完全放弃更好
3. **全面测试**: 需要用多个不同的源PDF测试，覆盖各种边缘情况

### 相关文件
- `E:\宝贝\口袋单词本\generate_pocket_book.py` - 主脚本
- `C:\Users\YAN-Hengyu\.claude\skills\pocket-book\scripts\generate_pocket_book.py` - Skill脚本（已同步）

---

## Bug #1: 第128和195条字体仍然很小

**报告时间**: 2026-03-14
**状态**: ✅ 已解决

### 问题描述
用户反馈第128条和第195条的字体仍然很小，要求字体区域占总体三分之二以上，但修改触发阈值后无明显效果。

### 根本原因
第128条包含过长的英文单词（如"available"），在原始字体大小（size=14）和卡片宽度46mm的情况下，fpdf2的`write_html`方法抛出异常：`FPDFException: Not enough horizontal space to render a single character`。这导致：
1. 初始测量失败（返回错误值）
2. 无法进行二分搜索放大
3. 最终使用原始字体或被错误缩小

### 最终解决方案

#### 修改1：降低初始字体大小
**文件**: `generate_pocket_book.py`
**位置**: HTML生成部分（约164行和200行）
```python
# 标题字体：14 → 10
html.append(f'<font size="10"><b>{title_html}</b></font><br>')

# 内容字体：12 → 9
html.append(f'<font size="9">{prefix_html}{block_html}</font><br>')
```
**原因**: 较小的初始字体确保所有内容都能在46mm宽度下成功渲染和测量。

#### 修改2：智能回退策略
**文件**: `generate_pocket_book.py`
**位置**: `draw_word_card`方法的二分搜索部分（约400行）
```python
# 在二分搜索中，当测量失败（trial_h < 0）时：
if trial_h < 0:
    # 测量失败，说明这个缩放太大了
    hi = mid
    failed_count += 1
elif trial_h <= max_h * 0.98:
    best_html = trial_html
    best_scale = mid
    lo = mid
else:
    hi = mid
```
**原因**: 当放大到某个倍数后无法渲染时，自动回退到最大可成功渲染的缩放因子，而不是放弃放大。

#### 修改3：移除触发阈值限制
**文件**: `generate_pocket_book.py`
**位置**: `draw_word_card`方法的缩放判断（约395行）
```python
# 原来：elif measured_h < target_fill * 0.85 and measured_h > 0:
# 修改为：
elif measured_h < target_fill and measured_h > 0:
```
**原因**: 确保所有低于95%填充的内容都会被放大，而不是只放大低于80.75%的内容。

### 修复效果
- **第128条**: 从初始49.2%放大到约82%（1.66倍缩放）
- **第195条**: 从初始39.6%放大到97.9%（1.78倍缩放）
- **其他条目**: 普遍获得更大的字体和更高的空间利用率

### 经验教训
1. **HTML渲染限制**: fpdf2在窄宽度下无法渲染过长的单词，需要使用较小的初始字体
2. **错误处理**: 测量失败时不应返回极端值（如999），应返回-1并优雅处理
3. **智能回退**: 二分搜索应该能处理部分失败的情况，找到最大可用值
4. **调试重要性**: 添加详细的调试输出帮助快速定位问题根源

### 相关文件
- `E:\宝贝\口袋单词本\generate_pocket_book.py` - 主脚本
- `C:\Users\YAN-Hengyu\.claude\skills\pocket-book\scripts\generate_pocket_book.py` - Skill脚本（已同步）
- `C:\Users\YAN-Hengyu\.claude\skills\pocket-book\SKILL.md` - Skill定义（无需修改）
