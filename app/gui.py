#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import os
import queue
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

from PIL import Image, ImageTk

APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent
CORE_DIR = PROJECT_DIR / "skill" / "scripts"
for directory in (str(APP_DIR), str(CORE_DIR)):
    if directory not in sys.path:
        sys.path.insert(0, directory)

if getattr(sys, "frozen", False):
    bundle_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    os.environ["PATH"] = str(bundle_dir) + os.pathsep + os.environ.get("PATH", "")

import video_to_ppt
from make_ppt import VIDEO_EXTENSIONS, build_presentation, list_images


class QueueWriter:
    def __init__(self, log_queue: queue.Queue[str]):
        self.queue = log_queue

    def write(self, text: str) -> int:
        if text.strip():
            self.queue.put(text.rstrip())
        return len(text)

    def flush(self) -> None:
        return None


class ImagePreviewDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, images: list[Path], fit_var: tk.StringVar) -> None:
        super().__init__(parent)
        self.title("图片预览")
        self.geometry("920x560")
        self.minsize(760, 480)
        self.transient(parent)

        self.images = images
        self.fit_var = fit_var
        self.current_index = 0
        self.source_image: Image.Image | None = None
        self.preview_photo: ImageTk.PhotoImage | None = None
        self.render_job: str | None = None
        self.trace_name: str | None = None

        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)

        list_frame = ttk.LabelFrame(root, text="页面顺序", padding=8)
        list_frame.grid(row=0, column=0, sticky=tk.NS, padx=(0, 12))
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.image_list = tk.Listbox(
            list_frame, width=34, height=20, activestyle="dotbox", exportselection=False
        )
        self.image_list.grid(row=0, column=0, sticky=tk.NSEW)
        list_scrollbar = ttk.Scrollbar(list_frame, command=self.image_list.yview)
        list_scrollbar.grid(row=0, column=1, sticky=tk.NS)
        self.image_list.configure(yscrollcommand=list_scrollbar.set)
        self.image_list.bind("<<ListboxSelect>>", self._select_image)

        preview_frame = ttk.LabelFrame(root, text="幻灯片预览", padding=8)
        preview_frame.grid(row=0, column=1, sticky=tk.NSEW)
        preview_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        self.preview_canvas = tk.Canvas(
            preview_frame,
            width=640,
            height=360,
            background="white",
            highlightthickness=0,
        )
        self.preview_canvas.grid(row=0, column=0, sticky=tk.NSEW)

        self.info_var = tk.StringVar()
        ttk.Label(preview_frame, textvariable=self.info_var).grid(
            row=1, column=0, sticky=tk.W, pady=(6, 0)
        )

        for index, image_path in enumerate(self.images, start=1):
            self.image_list.insert(tk.END, f"{index:03d}  {image_path.name}")
        self.image_list.selection_set(0)
        self.image_list.activate(0)

        self.trace_name = self.fit_var.trace_add(
            "write", lambda *_: self._schedule_render()
        )
        self.bind("<Configure>", lambda _event: self._schedule_render())
        self._load_current()
        self.after_idle(self._render)

    def destroy(self) -> None:
        if self.render_job is not None:
            self.after_cancel(self.render_job)
            self.render_job = None
        if self.trace_name:
            self.fit_var.trace_remove("write", self.trace_name)
        super().destroy()

    def _select_image(self, _event: tk.Event[tk.Listbox]) -> None:
        selection = self.image_list.curselection()
        if not selection:
            return
        self.current_index = selection[0]
        self._load_current()
        self._render()

    def _load_current(self) -> None:
        image_path = self.images[self.current_index]
        try:
            with Image.open(image_path) as image:
                image.load()
                self.source_image = image.copy()
            self.info_var.set(
                f"{image_path.name}  {self.source_image.width} x {self.source_image.height}"
            )
        except Exception as exc:
            self.source_image = None
            self.info_var.set(f"{image_path.name}  无法读取")
            messagebox.showerror("预览错误", f"无法读取图片：\n{image_path}\n\n{exc}")

    def _schedule_render(self) -> None:
        if self.render_job is not None:
            self.after_cancel(self.render_job)
        self.render_job = self.after(80, self._render)

    def _render(self) -> None:
        self.render_job = None
        self.preview_canvas.update_idletasks()
        canvas_width = max(1, self.preview_canvas.winfo_width())
        canvas_height = max(1, self.preview_canvas.winfo_height())
        self.preview_canvas.delete("all")

        if self.source_image is None:
            return
        if canvas_width <= 1 or canvas_height <= 1:
            return

        source_width = self.source_image.width
        source_height = self.source_image.height
        resample = getattr(Image, "Resampling", Image).LANCZOS

        if self.fit_var.get() == "cover":
            source_aspect = source_width / source_height
            canvas_aspect = canvas_width / canvas_height
            if source_aspect > canvas_aspect:
                crop_width = int(source_height * canvas_aspect)
                crop_left = (source_width - crop_width) // 2
                crop_box = (crop_left, 0, crop_left + crop_width, source_height)
            else:
                crop_height = int(source_width / canvas_aspect)
                crop_top = (source_height - crop_height) // 2
                crop_box = (0, crop_top, source_width, crop_top + crop_height)
            display = self.source_image.crop(crop_box).resize(
                (canvas_width, canvas_height), resample
            )
            x = 0
            y = 0
        else:
            scale = min(canvas_width / source_width, canvas_height / source_height)
            display_width = max(1, int(source_width * scale))
            display_height = max(1, int(source_height * scale))
            display = self.source_image.resize((display_width, display_height), resample)
            x = (canvas_width - display_width) // 2
            y = (canvas_height - display_height) // 2

        self.preview_photo = ImageTk.PhotoImage(display)
        self.preview_canvas.create_image(x, y, anchor=tk.NW, image=self.preview_photo)


class VideoToPptApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Video to PPT")
        self.geometry("760x620")
        self.minsize(700, 560)

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.started_at: float | None = None

        self.source_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.force_var = tk.StringVar()
        self.exclude_software_var = tk.BooleanVar(value=True)
        self.image_fit_var = tk.StringVar(value="fit")

        self._build_ui()
        self.after(100, self._poll_log_queue)

    def _build_ui(self) -> None:
        padding = {"padx": 12, "pady": 5}
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(1, weight=1)

        ttk.Label(root, text="输入").grid(row=0, column=0, sticky=tk.W, **padding)
        source_entry = ttk.Entry(root, textvariable=self.source_var)
        source_entry.grid(row=0, column=1, sticky=tk.EW, **padding)
        source_entry.bind("<FocusOut>", lambda _event: self._update_default_output())
        ttk.Button(root, text="选视频", command=self.choose_video).grid(
            row=0, column=2, **padding
        )
        ttk.Button(root, text="选图片", command=self.choose_image_folder).grid(
            row=1, column=2, **padding
        )

        ttk.Label(root, text="输出").grid(row=2, column=0, sticky=tk.W, **padding)
        ttk.Entry(root, textvariable=self.output_var).grid(
            row=2, column=1, sticky=tk.EW, **padding
        )
        ttk.Button(root, text="选择", command=self.choose_output).grid(
            row=2, column=2, **padding
        )

        ttk.Label(root, text="补页时间").grid(row=3, column=0, sticky=tk.W, **padding)
        ttk.Entry(root, textvariable=self.force_var).grid(
            row=3, column=1, columnspan=2, sticky=tk.EW, **padding
        )
        ttk.Label(root, text="多个时间点用逗号分隔，支持 73:49、01:13:49 或 4429").grid(
            row=4, column=1, columnspan=2, sticky=tk.W, padx=12
        )

        ttk.Checkbutton(
            root,
            text="排除纯软件演示画面",
            variable=self.exclude_software_var,
        ).grid(row=5, column=1, columnspan=2, sticky=tk.W, padx=12, pady=8)

        image_layout = ttk.LabelFrame(root, text="图片排版", padding=(12, 6))
        image_layout.grid(row=6, column=1, columnspan=2, sticky=tk.EW, padx=12)
        ttk.Radiobutton(
            image_layout,
            text="完整显示",
            value="fit",
            variable=self.image_fit_var,
        ).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Radiobutton(
            image_layout,
            text="填满裁剪",
            value="cover",
            variable=self.image_fit_var,
        ).pack(side=tk.LEFT)

        buttons = ttk.Frame(root)
        buttons.grid(row=7, column=1, columnspan=2, sticky=tk.E, padx=12, pady=8)
        self.start_button = ttk.Button(buttons, text="开始生成", command=self.start)
        self.start_button.pack(side=tk.LEFT, padx=(0, 8))
        self.preview_button = ttk.Button(buttons, text="预览", command=self.preview)
        self.preview_button.pack(side=tk.LEFT, padx=(0, 8))
        self.open_button = ttk.Button(
            buttons, text="打开输出文件夹", command=self.open_output_folder, state=tk.DISABLED
        )
        self.open_button.pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="待选择输入")
        ttk.Label(root, textvariable=self.status_var).grid(
            row=8, column=1, columnspan=2, sticky=tk.W, padx=12
        )

        log_frame = ttk.LabelFrame(root, text="处理日志", padding=8)
        log_frame.grid(row=9, column=0, columnspan=3, sticky=tk.NSEW, **padding)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        root.rowconfigure(9, weight=1)

        self.log_text = tk.Text(log_frame, height=12, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.grid(row=0, column=0, sticky=tk.NSEW)
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def choose_video(self) -> None:
        source = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[
                ("支持的文件", " ".join(f"*{suffix}" for suffix in sorted(VIDEO_EXTENSIONS))),
                ("所有文件", "*.*"),
            ],
        )
        if source:
            self.source_var.set(source)
            self._update_default_output()

    def choose_image_folder(self) -> None:
        source = filedialog.askdirectory(title="选择图片文件夹")
        if source:
            self.source_var.set(source)
            self._update_default_output()

    def choose_output(self) -> None:
        output = filedialog.asksaveasfilename(
            title="保存 PPTX",
            defaultextension=".pptx",
            filetypes=[("PowerPoint 文件", "*.pptx"), ("所有文件", "*.*")],
        )
        if output:
            self.output_var.set(output)

    def preview(self) -> None:
        source = Path(self.source_var.get().strip()).expanduser()
        if not source.is_dir():
            messagebox.showinfo("预览", "当前预览支持图片文件夹。")
            return
        try:
            images = list_images(source)
        except ValueError as exc:
            messagebox.showerror("预览错误", str(exc))
            return
        if not images:
            messagebox.showerror("预览错误", "文件夹里没有找到图片。")
            return
        ImagePreviewDialog(self, images, self.image_fit_var)

    def _update_default_output(self) -> None:
        source_text = self.source_var.get().strip()
        if not source_text:
            return
        source = Path(source_text).expanduser()
        if source.is_dir():
            self.output_var.set(str(source.parent / f"{source.name}_16x9.pptx"))
        elif source.suffix.lower() in VIDEO_EXTENSIONS:
            self.output_var.set(str(source.with_suffix(".pptx")))

    def append_log(self, message: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _poll_log_queue(self) -> None:
        while True:
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                break
            if message == "DONE":
                self._finish(True)
            elif message.startswith("FAILED:"):
                self.append_log("处理失败。")
                self._finish(False)
            else:
                self.append_log(message)

        if self.started_at is not None and self.worker and self.worker.is_alive():
            elapsed = int(time.monotonic() - self.started_at)
            self.status_var.set(f"处理中，已运行 {elapsed // 60:02d}:{elapsed % 60:02d}")
        self.after(100, self._poll_log_queue)

    def parse_force_times(self) -> list[float]:
        raw_values = self.force_var.get().replace("，", ",").replace("\n", ",")
        values = [item.strip() for item in raw_values.split(",") if item.strip()]
        return [video_to_ppt.parse_time(value) for value in values]

    def start(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("正在处理", "当前任务还没有结束。")
            return

        source = Path(self.source_var.get().strip()).expanduser()
        output = Path(self.output_var.get().strip()).expanduser()
        is_video = source.is_file() and source.suffix.lower() in VIDEO_EXTENSIONS
        is_image_folder = source.is_dir()
        if not (is_video or is_image_folder):
            messagebox.showerror("输入错误", "请选择视频文件或图片文件夹。")
            return
        if output.suffix.lower() != ".pptx":
            messagebox.showerror("输出错误", "输出文件必须以 .pptx 结尾。")
            return
        if output.exists() and not messagebox.askyesno(
            "覆盖确认", f"输出文件已存在，是否覆盖？\n{output}"
        ):
            return

        force_times: list[float] = []
        if is_video:
            try:
                force_times = self.parse_force_times()
            except Exception as exc:
                messagebox.showerror("补页时间错误", str(exc))
                return

        self.open_button.configure(state=tk.DISABLED)
        self.start_button.configure(state=tk.DISABLED)
        self.started_at = time.monotonic()
        self.status_var.set("处理中")
        self.append_log(f"输入：{source}")
        self.append_log(f"输出：{output}")

        target = self.run_video if is_video else self.run_images
        args: tuple[Path, Path, list[float], bool] | tuple[
            Path, Path, list[float], bool, str
        ]
        if is_image_folder:
            args = (
                source,
                output,
                force_times,
                self.exclude_software_var.get(),
                self.image_fit_var.get(),
            )
        else:
            args = (source, output, force_times, self.exclude_software_var.get())
        self.worker = threading.Thread(
            target=target,
            args=args,
            daemon=True,
        )
        self.worker.start()

    def run_images(
        self,
        source: Path,
        output: Path,
        _force_times: list[float],
        _exclude: bool,
        fit_mode: str = "fit",
    ) -> None:
        writer = QueueWriter(self.log_queue)
        try:
            with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                result = build_presentation(source, output, fit_mode=fit_mode)
            self.log_queue.put(f"生成文件：{result}")
            self.log_queue.put("DONE")
        except Exception:
            self.log_queue.put(traceback.format_exc())
            self.log_queue.put("FAILED:exception")

    def run_video(
        self, source: Path, output: Path, force_times: list[float], exclude_software: bool
    ) -> None:
        command = [str(source), "--output", str(output)]
        for seconds in force_times:
            command.extend(["--force-time", video_to_ppt.format_time(seconds)])
        if not exclude_software:
            command.append("--no-software-exclusion")

        writer = QueueWriter(self.log_queue)
        try:
            with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                result = video_to_ppt.main(command)
            self.log_queue.put("DONE" if result == 0 else f"FAILED:{result}")
        except Exception:
            self.log_queue.put(traceback.format_exc())
            self.log_queue.put("FAILED:exception")

    def open_output_folder(self) -> None:
        output = Path(self.output_var.get().strip()).expanduser()
        if not output.is_file():
            messagebox.showerror("未找到输出", "输出文件还不存在。")
            return
        folder = str(output.parent)
        if sys.platform == "win32":
            os.startfile(folder)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])

    def _finish(self, success: bool) -> None:
        self.started_at = None
        self.start_button.configure(state=tk.NORMAL)
        if success:
            self.status_var.set("完成")
            self.open_button.configure(state=tk.NORMAL)
        else:
            self.status_var.set("失败")
            self.open_button.configure(state=tk.DISABLED)


def configure_windows_dpi() -> None:
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


def main() -> None:
    configure_windows_dpi()
    app = VideoToPptApp()
    app.mainloop()


if __name__ == "__main__":
    main()
