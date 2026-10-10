# Video to PPT

从录屏或分享视频中提取 PPT 页面，生成 16:9 PPTX。工具会自动识别演示区域、合并重复页、排除纯软件演示画面，并保留 PPT 中嵌入的软件截图。

## 功能

- 默认 2 fps 抽帧，降低短停留页面漏检概率。
- 自动识别演示区域，也支持手动裁剪。
- 使用灰度均值差、dHash 和 RGB 直方图合并重复页。
- 保守排除纯软件演示画面；不确定页面默认保留。
- `--force-time` 强制补页，并按时间顺序插入。
- 输出前执行严格递增校验，避免补页被追加到末尾。
- 生成 `manifest.tsv`、`report.json` 和 `review/contact_sheet.jpg`，便于复核漏页和排除原因。
- 桌面应用支持拖入图片文件夹或视频文件。

## Windows 桌面应用

从 GitHub Releases 下载 `VideoToPPT.exe` 后可以直接运行。EXE 内置 Python 依赖、FFmpeg 和 FFprobe，不需要另装 Python。

界面支持：

- 选择视频文件或图片文件夹，生成 16:9 PPTX。
- 输入多个强制补页时间点，例如 `73:49, 74:49`。
- 选择是否排除纯软件演示画面。
- 查看处理日志，完成后打开输出文件夹。

Windows 版由 GitHub Actions 构建，流程见 `.github/workflows/windows.yml`。

## 本地安装

需要 Python 3.11+、FFmpeg，以及 Python 依赖：

```bash
brew install ffmpeg
python3 -m pip install -r requirements.txt
```

安装 Codex Skill：

```bash
./install_skill.sh
```

构建 macOS 桌面应用：

```bash
./app/build_app.sh
```

构建完成后会生成 `图片视频合成PPT.app`。应用会自动查找已安装依赖的 Python，也可以用环境变量指定：

```bash
VIDEO_TO_PPT_PYTHON=/path/to/python ./app/build_app.sh
```

Windows 本地构建需要安装 Python、FFmpeg 和 PyInstaller，然后执行：

```powershell
python -m pip install -r requirements.txt pyinstaller
pyinstaller --onefile --windowed --name VideoToPPT --paths skill/scripts --paths app app/gui.py
```

如需开箱即用，还要把本机的 `ffmpeg.exe` 和 `ffprobe.exe` 用 `--add-binary` 加入打包命令。

## 命令行用法

```bash
python3 skill/scripts/video_to_ppt.py INPUT.mp4
```

强制补页：

```bash
python3 skill/scripts/video_to_ppt.py INPUT.mp4 \
  --force-time 01:13:49 \
  --force-time 01:14:49
```

手动指定演示区域：

```bash
python3 skill/scripts/video_to_ppt.py INPUT.mp4 --crop 304,80,976,610
```

常用输出：

- `OUTPUT.pptx`
- `WORKDIR/manifest.tsv`
- `WORKDIR/report.json`
- `WORKDIR/review/contact_sheet.jpg`

## 复核流程

1. 先看 `contact_sheet.jpg`，确认页面顺序和是否有漏页。
2. 再看 `manifest.tsv`，核对每页的时间戳、稳定区间、软件演示分数和排除原因。
3. 发现漏页时，用 `--force-time` 指定时间点重跑。
4. 如果纯软件演示画面混入成品，先检查该页是否仍有幻灯片边界；不要仅因为页面里有软件截图就调低阈值。

## 仓库结构

- `skill/`：Codex Skill 源码。
- `app/`：macOS 桌面应用源码和构建脚本。
- `install_skill.sh`：安装 Skill 到本机 Codex 目录。
- `requirements.txt`：Python 依赖。

## 许可

MIT License。

Windows 发布版捆绑 BtbN 的 FFmpeg GPL 构建，详见 `THIRD_PARTY.md`。
