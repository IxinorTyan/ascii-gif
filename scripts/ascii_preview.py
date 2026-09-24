"""A nonblocking single-frame timeline preview for the HTML exporter."""
import queue
import threading
import tkinter as tk
from tkinter import ttk

from PIL import ImageTk

from ascii_html import media_frame_count, preview_frame, frame_range, css_color


class AsciiPreview(tk.Toplevel):
    def __init__(self, parent, source, settings_getter):
        super().__init__(parent)
        self.title('ASCII 动画预览 — 拖动时间轴查看一帧')
        self.geometry('1100x700')
        self.minsize(850, 500)
        self.source = source
        self.settings_getter = settings_getter
        self.events = queue.Queue()
        self.busy = False
        self.pending = False
        self.closed = False
        self.poll_id = None
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        ttk.Label(self, text='拖动后松开即渲染；在主窗口调整参数后，点击“重新渲染当前帧”。\n'
                  '预览与导出使用相同字符数据；字体排版以浏览器为准。',
                  style='New.TLabel').grid(row=0, column=0, sticky='ew', padx=12, pady=8)
        panes = ttk.Panedwindow(self, orient='horizontal')
        panes.grid(row=1, column=0, sticky='nsew', padx=12)
        original = ttk.LabelFrame(panes, text='原始帧（缩略图）')
        self.original = ttk.Label(original, anchor='center')
        self.original.pack(fill='both', expand=True)
        panes.add(original, weight=1)
        converted = ttk.LabelFrame(panes, text='ASCII 字符（可滚动、可复制）')
        converted.columnconfigure(0, weight=1)
        converted.rowconfigure(0, weight=1)
        self.text = tk.Text(converted, wrap='none', font=('Consolas', -10),
                            state='disabled', padx=8, pady=8, spacing1=0, spacing3=0)
        self.text.grid(row=0, column=0, sticky='nsew')
        horizontal = ttk.Scrollbar(converted, orient='horizontal', command=self.text.xview)
        vertical = ttk.Scrollbar(converted, orient='vertical', command=self.text.yview)
        horizontal.grid(row=1, column=0, sticky='ew')
        vertical.grid(row=0, column=1, sticky='ns')
        self.text.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)
        panes.add(converted, weight=3)

        self.selection = ttk.Label(self, text='正在读取帧数…', style='New.TLabel')
        self.selection.grid(row=2, column=0, sticky='ew', padx=12, pady=6)
        self.timeline = tk.Scale(self, from_=0, to=0, orient='horizontal',
                                 resolution=1, showvalue=False, state='disabled',
                                 command=self.select_frame)
        self.timeline.grid(row=3, column=0, sticky='ew', padx=12)
        self.timeline.bind('<ButtonRelease-1>', lambda event: self.render())
        self.timeline.bind('<KeyRelease>', lambda event: self.render())
        controls = ttk.Frame(self)
        controls.grid(row=4, column=0, sticky='ew', padx=12, pady=8)
        self.buttons = []
        for label, command in [('上一帧', lambda: self.step(-1)),
                               ('下一帧', lambda: self.step(1)),
                               ('重新渲染当前帧', self.render)]:
            button = ttk.Button(controls, text=label, command=command, style='New2.TButton', state='disabled')
            button.pack(side='left', padx=4)
            self.buttons.append(button)
        ttk.Label(controls, text='预览字号', style='New.TLabel').pack(side='left', padx=8)
        size = tk.Scale(controls, from_=4, to=24, orient='horizontal',
                        command=lambda value: self.text.configure(font=('Consolas', -int(value))))
        size.set(10)
        size.pack(side='left')
        self.status = ttk.Label(self, text='正在加载…', style='New.TLabel', wraplength=1000)
        self.status.grid(row=5, column=0, sticky='ew', padx=12, pady=8)
        self.launch('loaded', lambda: media_frame_count(source))
        self.poll_id = self.after(60, self.poll)

    def launch(self, kind, work):
        self.busy = True

        def worker():
            try:
                self.events.put((kind, work()))
            except Exception as error:
                self.events.put(('error', str(error)))

        threading.Thread(target=worker, daemon=True).start()

    def select_frame(self, value):
        self.selection.configure(text=f'选中第 {int(float(value))} 帧（帧编号从 0 开始）')

    def step(self, delta):
        self.timeline.set(max(int(self.timeline.cget('from')), min(
            int(self.timeline.cget('to')), self.timeline.get() + delta)))
        self.render()

    def render(self):
        if self.closed or not hasattr(self, 'total'):
            return
        if self.busy:
            self.pending = True
            return
        try:
            settings, cell_size = self.settings_getter()
            start, end = frame_range(settings.get('video_frames_interval'))
            end = self.total if end is None else min(end, self.total)
            if start >= end:
                raise ValueError('帧范围内没有可预览的帧。')
            self.timeline.configure(from_=start, to=end - 1, state='normal')
            index = max(start, min(end - 1, self.timeline.get()))
            self.timeline.set(index)
            self.select_frame(index)
            foreground = css_color(settings['ascii_image_character_color'])
            background = css_color(settings['ascii_image_init_bg_color'])
        except Exception as error:
            self.status.configure(text='预览失败：' + str(error))
            return
        self.status.configure(text=f'正在渲染第 {index} 帧…')

        def work():
            image, frame, duration = preview_frame(self.source, index, settings, cell_size)
            image.thumbnail((280, 400))
            return index, image, frame, duration, foreground, background

        self.launch('frame', work)

    def show_frame(self, value):
        index, image, frame, duration, foreground, background = value
        self.photo = ImageTk.PhotoImage(image)
        self.original.configure(image=self.photo)
        self.text.configure(state='normal', background=background, foreground=foreground)
        self.text.delete('1.0', 'end')
        for tag in self.text.tag_names():
            if tag != 'sel':
                self.text.tag_delete(tag)
        self.text.insert('1.0', frame['text'])
        if frame['colors']:
            # Tag same-color runs, avoiding one Tk call per character where possible.
            offset = 0
            for row_index, row in enumerate(frame['text'].split('\n'), 1):
                start = 0
                while start < len(row):
                    color = frame['colors'][offset + start]
                    end = start + 1
                    while end < len(row) and frame['colors'][offset + end] == color:
                        end += 1
                    self.text.tag_configure(color, foreground=color)
                    self.text.tag_add(color, f'{row_index}.{start}', f'{row_index}.{end}')
                    start = end
                offset += len(row)
        self.text.configure(state='disabled')
        rows = frame['text'].split('\n')
        self.status.configure(text=f'已渲染第 {index} 帧 / 共 {self.total} 帧 · '
                              f'{len(rows[0])} 列 × {len(rows)} 行 · 本帧时长 {duration:g} 毫秒')

    def poll(self):
        if self.closed:
            return
        try:
            kind, value = self.events.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            if kind == 'loaded':
                self.total = value
                for button in self.buttons:
                    button.configure(state='normal')
                self.render()
            elif kind == 'frame':
                if not self.pending:
                    self.show_frame(value)
            else:
                self.status.configure(text='预览失败：' + value)
            if self.pending:
                self.pending = False
                self.render()
        self.poll_id = self.after(60, self.poll)

    def close(self):
        self.closed = True
        if self.poll_id is not None:
            self.after_cancel(self.poll_id)
        self.destroy()
