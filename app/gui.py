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
from make_ppt import VIDEO_EXTENSIONS, build_presentation


class QueueWriter:
    def __init__(self, log_queue: queue.Queue[str]):
        self.queue = log_queue

    def write(self, text: str) -> int:
        if text.strip():
            self.queue.put(text.rstrip())
        return len(text)

    def flush(self) -> None:
        return None


class VideoToPptApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Video to PPT")
        self.geometry("760x560")
        self.minsize(680, 500)

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.started_at: float | None = None

        self.source_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.force_var = tk.StringVar()
        self.exclude_software_var = tk.BooleanVar(value=True)

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

        buttons = ttk.Frame(root)
        buttons.grid(row=6, column=1, columnspan=2, sticky=tk.E, padx=12, pady=8)
        self.start_button = ttk.Button(buttons, text="开始生成", command=self.start)
        self.start_button.pack(side=tk.LEFT, padx=(0, 8))
        self.open_button = ttk.Button(
            buttons, text="打开输出文件夹", command=self.open_output_folder, state=tk.DISABLED
        )
        self.open_button.pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="待选择输入")
        ttk.Label(root, textvariable=self.status_var).grid(
            row=7, column=1, columnspan=2, sticky=tk.W, padx=12
        )

        log_frame = ttk.LabelFrame(root, text="处理日志", padding=8)
        log_frame.grid(row=8, column=0, columnspan=3, sticky=tk.NSEW, **padding)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        root.rowconfigure(8, weight=1)

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
        self.worker = threading.Thread(
            target=target,
            args=(source, output, force_times, self.exclude_software_var.get()),
            daemon=True,
        )
        self.worker.start()

    def run_images(
        self, source: Path, output: Path, _force_times: list[float], _exclude: bool
    ) -> None:
        writer = QueueWriter(self.log_queue)
        try:
            with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                result = build_presentation(source, output)
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
