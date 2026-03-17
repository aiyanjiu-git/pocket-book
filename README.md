# 口袋单词本自动排版工具

将 PDF 单词表一键转换为可打印的 A4 口袋书。

## 功能特点

- 📖 自动解析 PDF 单词表
- 🎨 智能颜色着色（红色编号、黑色中文、蓝色英文）
- 📏 智能字体缩放（填充 2/3+ 卡片空间）
- 📑 A4 口袋书排版（16页/册，saddle stitch）
- 🔢 支持非连续编号和特殊格式

## 安装依赖

```bash
pip install PyMuPDF fpdf2
```

## 使用方法

1. 将 PDF 文件放入 `input/` 文件夹
2. 运行脚本：

```bash
python generate_pocket_book.py input/你的文件.pdf -o output
```

3. 在 `output/` 文件夹中获取生成的口袋书 PDF

## 打印说明

1. A4 纸【双面打印，翻转短边】
2. 剪掉四周白边，得到 20cm × 14cm 矩形
3. 沿网格十字线剪开，得到 4 张 10cm × 7cm 的双面纸条
4. 将每张纸条沿中间对折，按照封面图案嵌套在一起
5. 左侧装订，完美 16 面小册子完成！

## 技术栈

- Python 3.x
- PyMuPDF (fitz) - PDF 解析
- fpdf2 - PDF 生成

## 许可证

MIT
