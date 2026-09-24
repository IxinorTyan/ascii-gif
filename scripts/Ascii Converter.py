import json
import queue
import threading
from ascii_html import export_html, ExportCancelled
from ascii_preview import AsciiPreview

abs_path = os.getcwd()

settings_path = 'scripts/config.json'
with open(settings_path, encoding='utf-8') as f:
    current_settings = json.load(f)
def normalize_language(lang):
    if not lang:
        return 'Chinese'
    s = str(lang).strip().lower()
    if s in ['chinese', 'zh', 'zh-cn', 'zh-hans', '中文', '汉语', '简体中文']:
        return 'Chinese'
    elif s in ['english', 'en', 'en-us', '英文', '英语']:
        return 'English'
    return str(lang).strip()

globals().update(current_settings)
language = normalize_language(current_settings.get('language', 'Chinese'))
current_settings['language'] = language

try:
    with open(f'scripts/languages/{language}.json', encoding='utf-8') as f:
        translate_dict = json.load(f)
except:
    with open('scripts/languages/English.json', encoding='utf-8') as f:
        translate_dict = json.load(f)
translate_dict_reverse = {j: i for i, j in translate_dict.items()}


def change(var, new):
    current_settings[var] = new
    with open(settings_path, 'w', encoding='utf-8') as f:
        json.dump(current_settings,
                  f,
                  indent=4,
                  separators=(',', ': '),
                  ensure_ascii=False)


def get_value(text):
    try:
        value = literal_eval(text)
    except:
        value = text
    return value


class Root(Tk):

    def __init__(self):
        super(Root, self).__init__()
        self.value_dict = deepcopy(current_settings)
        self.title("Ascii Converter")
        self.minsize(1000, 650)
        self.wm_iconbitmap('resources/ascii.ico')
        self.set_style()
        self.update_font()
        try:
            bg_image = Image.open(background_image)
        except:
            bg_image = Image.open('resources/background.png')
        self.background_image = ImageTk.PhotoImage(
            bg_image.resize(
                (1000, int(1000 * (bg_image.height / bg_image.width)))))
        self.bg_label = ttk.Label(self, image=self.background_image)
        self.bg_label.place(x=0, y=0)
        title_image = Image.open('resources/title.png')
        self.title_image = ImageTk.PhotoImage(title_image.resize((456, 80)))
        self.title_label = ttk.Label(self,
                                     image=self.title_image,
                                     compound=CENTER)
        self.title_label.place(x=0, y=0)
        self.img_to_ascii_img_button = ttk.Button(
            self,
            text=translate_dict['Image to Ascii Images/Texts'],
            compound=CENTER,
            command=self.img_to_ascii_img_window)
        self.img_to_ascii_img_button.place(x=0, y=140, width=500, height=60)
        self.video_to_ascii_video_button = ttk.Button(
            self,
            text=translate_dict['Videos to Ascii Videos'],
            compound=CENTER,
            command=self.video_to_ascii_video_window)
        self.video_to_ascii_video_button.place(x=0,
                                               y=240,
                                               width=500,
                                               height=60)
        self.video_to_ascii_img_button = ttk.Button(
            self,
            text=translate_dict['Extract Frames From Videos'],
            compound=CENTER,
            command=self.video_to_img_window)
        self.video_to_ascii_img_button.place(x=0, y=340, width=500, height=60)
        self.change_settings_button = ttk.Button(
            self,
            text=translate_dict['Change Settings'],
            compound=CENTER,
            command=self.change_settings_window,
            style='New.TButton')
        self.change_settings_button.place(x=0, y=440, width=500, height=60)
        lang_text = "🌐 切换为 English" if self.value_dict.get('language') == 'Chinese' else "🌐 切换为 中文"
        self.toggle_language_button = ttk.Button(
            self,
            text=lang_text,
            compound=CENTER,
            command=self.toggle_language,
            style='New2.TButton')
        self.toggle_language_button.place(x=0, y=520, width=500, height=55)
        self.html_button = ttk.Button(self, text='视频 / GIF → ASCII 动画 HTML',
                                      command=self.ascii_html_window, style='New2.TButton')
        self.html_button.place(x=520, y=340, width=450, height=60)
        self.main_widgets = [
            self.img_to_ascii_img_button,
            self.video_to_ascii_video_button,
            self.video_to_ascii_img_button,
            self.change_settings_button,
            self.toggle_language_button,
            self.html_button
        ]
        self.frame_info = StringVar()
        self.frame_show = ttk.Label(self,
                                    textvariable=self.frame_info,
                                    style='New.TLabel',
                                    anchor='nw')
        self.var_counter = 1
        self.value_entry_dict = {}
        self.all_config_options = list(current_settings.keys())
        self.translate_all_config_options = [
            translate_dict[i] for i in self.all_config_options
        ]
        self.options_num = len(self.all_config_options)
        self.config_original = self.all_config_options.copy()
        self.all_config_options.sort(key=lambda s: s.lower())
        self.alpha_config = self.all_config_options.copy()
        self.go_back = False
        self.sort_mode = 1
        self.current_widgets = []

    def update_font(self):
        try:
            self.font = ImageFont.truetype(self.value_dict['font_path'],
                                           size=self.value_dict['font_size'])
        except:
            self.font = ImageFont.load_default()
        if hasattr(self.font, 'getbbox'):
            bbox = self.font.getbbox('a')
            font_x_len = max(1, bbox[2] - bbox[0])
            font_y_len = max(1, bbox[3] - bbox[1])
        elif hasattr(self.font, 'getsize'):
            font_x_len, font_y_len = self.font.getsize('a')
        else:
            font_x_len, font_y_len = 6, 11
        self.font_x_len = font_x_len
        self.font_y_len = font_y_len

    def set_style(self):
        self.current_font = translate_dict['font']
        style = ttk.Style()
        style.theme_use('alt')
        style.configure('TButton',
                        borderwidth=-2,
                        focuscolor='none',
                        highlightthickness=0,
                        font=(self.current_font, 18),
                        foreground='white',
                        background='forest green')
        style.map('TButton', background=[('active', 'lime green')])
        style.configure('New.TButton',
                        borderwidth=-2,
                        focuscolor='none',
                        highlightthickness=0,
                        font=(self.current_font, 18),
                        foreground='white',
                        background='dodger blue')
        style.map('New.TButton', background=[('active', 'deep sky blue')])
        style.configure('New2.TButton',
                        borderwidth=-2,
                        focuscolor='none',
                        highlightthickness=0,
                        font=(self.current_font, 12),
                        foreground='white',
                        background='forest green')
        style.map('New2.TButton', background=[('active', 'deep sky blue')])
        style.configure('TEntry',
                        fieldbackground='white',
                        foreground='black',
                        insertcolor='black')
        style.configure('TLabelframe',
                        background='black',
                        borderwidth=0,
                        focuscolor='none',
                        highlightthickness=0,
                        font=(self.current_font, 12))
        style.configure('TLabelframe.Label',
                        background='black',
                        foreground='white',
                        borderwidth=0,
                        focuscolor='none',
                        highlightthickness=0,
                        font=(self.current_font, 12))
        style.configure('TLabel',
                        background='white',
                        foreground='black',
                        borderwidth=0,
                        focuscolor='none',
                        highlightthickness=0,
                        font=(self.current_font, 12))
        style.configure('New.TLabel',
                        background='white',
                        foreground='black',
                        borderwidth=0,
                        focuscolor='none',
                        highlightthickness=0,
                        font=(self.current_font, 10))
        style.configure('TCheckbutton',
                        background='white',
                        foreground='black',
                        borderwidth=0,
                        focuscolor='none',
                        highlightthickness=0,
                        inactiveselectbackground='black',
                        font=(self.current_font, 12))
        style.configure('TScrollbar', background='white')

    def img_to_ascii_img_window(self):
        self.go_back = False
        self.quit_main_window()
        self.current_widgets = []

        self.go_back_button = ttk.Button(self,
                                         text=translate_dict['Back'],
                                         command=self.go_back_main_window,
                                         compound=CENTER,
                                         style='New.TButton')
        self.go_back_button.place(x=500, y=560, width=400, height=50)
        self.current_widgets.append(self.go_back_button)

        self.save_as_ascii_text_button = ttk.Button(
            self,
            text=translate_dict['image → ascii text'],
            command=self.image_to_ascii_text,
            compound=CENTER)
        self.save_as_ascii_text_button.place(x=0, y=480, width=400, height=50)
        self.current_widgets.append(self.save_as_ascii_text_button)

        self.save_as_ascii_image_button = ttk.Button(
            self,
            text=translate_dict['image → ascii image'],
            command=self.image_to_ascii_image,
            compound=CENTER)
        self.save_as_ascii_image_button.place(x=0, y=560, width=400, height=50)
        self.current_widgets.append(self.save_as_ascii_image_button)

        self.current_widgets += self.set_value('image path', 'image_path', 600,
                                               50, 0, 115, True)
        self.current_widgets += self.set_value('resize ratio', 'resize_ratio',
                                               120, 28, 0, 220)
        self.current_widgets += self.set_value('bit number', 'bit_number', 120,
                                               28, 0, 300)

        self.current_widgets += self.set_value('show convert percentages',
                                               'show_convert_percentages',
                                               200,
                                               40,
                                               200,
                                               220,
                                               mode=1,
                                               font_size=10)

        self.current_widgets += self.set_value('image width ratio',
                                               'image_width_ratio', 160, 28,
                                               200, 300)
        self.current_widgets += self.set_value('image height ratio',
                                               'image_height_ratio', 170, 28,
                                               450, 300)

        self.save_button = ttk.Button(
            self,
            text=translate_dict['Save Current Settings'],
            command=self.save_current,
            compound=CENTER,
            style='New.TButton')
        self.save_button.place(x=500, y=480, width=400, height=50)
        self.current_widgets.append(self.save_button)

        self.picture_color = IntVar()
        img_color = self.value_dict['colored_image']
        if type(img_color) == list:
            img_color = img_color[1]
        self.picture_color.set(1 if img_color else 0)
        self.output_picture_color = ttk.Checkbutton(
            self,
            text=translate_dict['colored_image'],
            variable=self.picture_color,
            command=lambda: self.change_bool('colored_image'))
        self.output_picture_color.var = self.picture_color
        self.output_picture_color.place(x=450, y=220, width=160, height=40)
        self.value_dict['colored_image'] = img_color
        self.value_entry_dict['colored_image'] = self.output_picture_color
        self.current_widgets.append(self.output_picture_color)

        self.frame_info.set(translate_dict['No actions at this time'])
        self.frame_show.place(x=0, y=380, width=300, height=70)
        self.current_widgets.append(self.frame_show)

    def video_to_ascii_video_window(self):
        self.go_back = False
        self.quit_main_window()
        self.current_widgets = []

        self.go_back_button = ttk.Button(self,
                                         text=translate_dict['Back'],
                                         command=self.go_back_main_window,
                                         compound=CENTER,
                                         style='New.TButton')
        self.go_back_button.place(x=500, y=560, width=400, height=50)
        self.current_widgets.append(self.go_back_button)

        self.start_video_to_ascii_video_button = ttk.Button(
            self,
            text=translate_dict['video → ascii video'],
            command=self.video_to_ascii_video,
            compound=CENTER)
        self.start_video_to_ascii_video_button.place(x=0,
                                                     y=480,
                                                     width=400,
                                                     height=50)
        self.current_widgets.append(self.start_video_to_ascii_video_button)

        self.start_video_frames_to_ascii_video_button = ttk.Button(
            self,
            text=translate_dict['frames → ascii video'],
            command=lambda: self.video_to_ascii_video(mode=1),
            compound=CENTER)
        self.start_video_frames_to_ascii_video_button.place(x=0,
                                                            y=560,
                                                            width=400,
                                                            height=50)
        self.current_widgets.append(
            self.start_video_frames_to_ascii_video_button)

        self.current_widgets += self.set_value('video path', 'video_path', 600,
                                               50, 0, 115, True)
        self.current_widgets += self.set_value('resize ratio', 'resize_ratio',
                                               120, 28, 0, 220)
        self.current_widgets += self.set_value('bit number', 'bit_number', 120,
                                               28, 0, 300)
        self.current_widgets += self.set_value('video frames interval',
                                               'video_frames_interval', 200,
                                               28, 160, 220)
        self.current_widgets += self.set_value('video frame rate',
                                               'video_frame_rate', 160, 28,
                                               160, 300)
        self.current_widgets += self.set_value('image width ratio',
                                               'image_width_ratio', 160, 28,
                                               400, 300)
        self.current_widgets += self.set_value('image height ratio',
                                               'image_height_ratio', 170, 28,
                                               600, 300)

        self.save_button = ttk.Button(
            self,
            text=translate_dict['Save Current Settings'],
            command=self.save_current,
            compound=CENTER,
            style='New.TButton')
        self.save_button.place(x=500, y=480, width=400, height=50)
        self.current_widgets.append(self.save_button)

        self.picture_color = IntVar()
        img_color = self.value_dict['colored_image']
        self.picture_color.set(1 if img_color else 0)
        self.output_picture_color = ttk.Checkbutton(
            self,
            text=translate_dict['colored_image'],
            variable=self.picture_color,
            command=lambda: self.change_bool('colored_image'))
        self.output_picture_color.var = self.picture_color
        self.output_picture_color.place(x=400, y=220, width=160, height=40)
        self.value_dict['colored_image'] = img_color
        self.value_entry_dict['colored_image'] = self.output_picture_color
        self.current_widgets.append(self.output_picture_color)

        self.frame_info.set(translate_dict['No actions at this time'])
        self.frame_show.place(x=0, y=380, width=300, height=70)
        self.current_widgets.append(self.frame_show)

    def ascii_html_window(self):
        self.video_to_ascii_video_window()
        self.start_video_to_ascii_video_button.configure(
            text='导出 ASCII 动画 HTML', command=self.start_html_export)
        self.start_video_frames_to_ascii_video_button.place_forget()
        # HTML uses source timing, independent of the existing MP4 output FPS.
        fps_entry = self.value_entry_dict['video_frame_rate']
        for widget in self.current_widgets:
            if widget is fps_entry or (isinstance(widget, ttk.Label)
                    and widget.cget('text') == translate_dict['video_frame_rate']):
                widget.place_forget()
        note = ttk.Label(self, text='选择视频或 GIF 文件；保留原始播放节奏，无音频。\n'
                         '帧范围留空为全部，或填写 [0, 100]（不含结束帧）。\n'
                         '导出后可离线播放；增大缩放倍数可以减小 HTML 体积。',
                         style='New.TLabel')
        note.place(x=0, y=550, width=490, height=75)
        self.current_widgets.append(note)
        self.frame_show.place(x=0, y=380, width=950, height=85)
        preview_button = ttk.Button(self, text='预览 / 选择一帧',
                                    command=self.open_html_preview, style='New2.TButton')
        preview_button.place(x=160, y=300, width=220, height=50)
        self.current_widgets.append(preview_button)

    def open_html_preview(self):
        source = self.value_dict.get('video_path')
        if not isinstance(source, str) or not os.path.isfile(source):
            self.frame_info.set('请先选择视频或 GIF 文件，再打开预览。')
            return
        existing = getattr(self, '_ascii_preview', None)
        if existing is not None and existing.winfo_exists():
            if existing.source == source:
                existing.lift()
                existing.render()
                return
            existing.close()

        def settings_getter():
            if self.value_dict.get('video_path') != source:
                raise ValueError('输入文件已改变，请在主窗口重新打开预览。')
            self.update_font()
            settings = deepcopy(self.value_dict)
            settings['colored_image'] = bool(self.picture_color.get())
            return settings, (self.font_x_len, self.font_y_len)

        self._ascii_preview = AsciiPreview(self, source, settings_getter)

    def start_html_export(self):
        if getattr(self, '_html_running', False):
            return
        settings = deepcopy(self.value_dict)
        settings['colored_image'] = bool(self.picture_color.get())
        source = settings.get('video_path')
        if not isinstance(source, str) or not os.path.isfile(source):
            self.frame_info.set('请选择存在的视频或 GIF 文件。')
            return
        destination = filedialog.asksaveasfilename(
            title='保存 ASCII 动画 HTML', defaultextension='.html',
            initialfile='ascii_' + os.path.splitext(os.path.basename(source))[0] + '.html',
            filetypes=(('HTML 网页', '*.html'),))
        if not destination:
            self.frame_info.set('已取消导出。')
            return
        self.update_font()
        cell_size = (self.font_x_len, self.font_y_len)
        self._html_running = True
        self._html_cancel = threading.Event()
        events = queue.Queue()
        self.start_video_to_ascii_video_button.configure(state='disabled')
        self.save_button.configure(state='disabled')
        self.go_back_button.configure(text='取消导出', command=self._html_cancel.set)
        self.frame_info.set('正在读取并转换为 ASCII 字符…')

        def worker():
            try:
                count = export_html(source, destination, settings, cell_size,
                                    lambda i, n: events.put(('progress', (i, n))),
                                    self._html_cancel.is_set)
                events.put(('done', count))
            except ExportCancelled:
                events.put(('cancelled', None))
            except Exception as error:
                events.put(('error', str(error)))

        def poll():
            latest = None
            while True:
                try:
                    latest = events.get_nowait()
                except queue.Empty:
                    break
            if latest:
                kind, value = latest
                if kind == 'progress':
                    index, total = value
                    self.frame_info.set(f'正在转换 ASCII 帧：{index} / {total or "未知"}')
                else:
                    self._html_running = False
                    self.start_video_to_ascii_video_button.configure(state='normal')
                    self.save_button.configure(state='normal')
                    self.go_back_button.configure(text=translate_dict['Back'], command=self.go_back_main_window)
                    if kind == 'done':
                        self.frame_info.set(f'已导出 {value} 帧，可用浏览器打开：\n{destination}')
                    elif kind == 'cancelled':
                        self.frame_info.set('已取消导出。')
                    else:
                        self.frame_info.set('导出失败：' + value)
                    return
            self.after(100, poll)

        threading.Thread(target=worker, daemon=True).start()
        self.after(100, poll)

    def video_to_img_window(self):
        self.go_back = False
        self.quit_main_window()
        self.current_widgets = []

        self.go_back_button = ttk.Button(self,
                                         text=translate_dict['Back'],
                                         command=self.go_back_main_window,
                                         compound=CENTER,
                                         style='New.TButton')
        self.go_back_button.place(x=500, y=560, width=400, height=50)
        self.current_widgets.append(self.go_back_button)

        self.start_video_to_frames_button = ttk.Button(
            self,
            text=translate_dict['video → frames'],
            command=self.video_to_img,
            compound=CENTER)
        self.start_video_to_frames_button.place(x=0,
                                                y=480,
                                                width=400,
                                                height=50)
        self.current_widgets.append(self.start_video_to_frames_button)

        self.current_widgets += self.set_value('video path', 'video_path', 600,
                                               50, 0, 115, True)
        self.current_widgets += self.set_value('video frames interval',
                                               'video_frames_interval', 200,
                                               28, 0, 220)
        self.picture_color = IntVar()
        self.picture_color.set(1)
        self.save_button = ttk.Button(
            self,
            text=translate_dict['Save Current Settings'],
            command=self.save_current,
            compound=CENTER,
            style='New.TButton')
        self.save_button.place(x=500, y=480, width=400, height=50)
        self.current_widgets.append(self.save_button)

        self.frame_info.set(translate_dict['No actions at this time'])
        self.frame_show.place(x=0, y=380, width=300, height=70)
        self.current_widgets.append(self.frame_show)

    def change_settings_window(self):
        self.go_back = False
        self.quit_main_window()
        self.go_back_button = ttk.Button(self,
                                         text=translate_dict['Back'],
                                         command=self.go_back_main_window,
                                         compound=CENTER,
                                         style='New.TButton')
        self.go_back_button.place(x=500, y=560, width=400, height=50)
        self.config_options_bar = ttk.Scrollbar(self)
        self.config_options_bar.place(x=228, y=191, height=183, anchor=CENTER)
        self.choose_config_options = Listbox(
            self,
            yscrollcommand=self.config_options_bar.set,
            background='white',
            foreground='black')
        self.choose_config_options.bind('<<ListboxSelect>>',
                                        self.show_current_config_options)
        self.choose_config_options.place(x=0, y=100, width=220)
        self.config_options_bar.config(
            command=self.choose_config_options.yview)
        self.config_name = ttk.Label(self, text='')
        self.already_place_config_name = False
        self.config_contents = Text(self,
                                    undo=True,
                                    autoseparators=True,
                                    maxundo=-1)
        self.config_contents.bind('<KeyRelease>', self.config_change)
        self.config_contents.place(x=400, y=145, width=380, height=170)
        self.choose_filename_button = ttk.Button(
            self,
            text=translate_dict['Choose filename'],
            command=self.choose_filename,
            compound=CENTER,
            style='New.TButton')
        self.choose_directory_button = ttk.Button(
            self,
            text=translate_dict['Choose directory'],
            command=self.choose_directory,
            compound=CENTER,
            style='New.TButton')
        self.choose_filename_button.place(x=0, y=480, width=400, height=50)
        self.choose_directory_button.place(x=0, y=560, width=400, height=50)
        self.save_button = ttk.Button(
            self,
            text=translate_dict['Save Current Settings'],
            command=self.save_current,
            compound=CENTER,
            style='New.TButton')
        self.save_button.place(x=500, y=480, width=400, height=50)
        self.search_text = ttk.Label(self,
                                     text=translate_dict['Search Settings'])
        self.search_text.place(x=0, y=400)
        self.search_contents = StringVar()
        self.search_contents.trace_add('write', self.search)
        self.search_entry = ttk.Entry(self, textvariable=self.search_contents)
        self.search_entry.place(x=0, y=425)
        self.search_inds = 0
        self.up_button = ttk.Button(
            self,
            text=translate_dict['Previous'],
            command=lambda: self.change_search_inds(-1),
            width=8,
            compound=CENTER,
            style='New.TButton')
        self.down_button = ttk.Button(
            self,
            text=translate_dict['Next'],
            command=lambda: self.change_search_inds(1),
            width=8,
            compound=CENTER,
            style='New.TButton')
        self.up_button.place(x=200, y=420, width=150, height=30)
        self.down_button.place(x=400, y=420, width=150, height=30)
        self.search_inds_list = []
        self.choose_bool1 = ttk.Button(
            self,
            text='True',
            command=lambda: self.insert_bool('True'),
            compound=CENTER)
        self.choose_bool2 = ttk.Button(
            self,
            text='False',
            command=lambda: self.insert_bool('False'),
            compound=CENTER)
        self.choose_bool1.place(x=200, y=370, width=150, height=30)
        self.choose_bool2.place(x=400, y=370, width=150, height=30)
        self.change_sort_button = ttk.Button(
            self,
            text=translate_dict['Sort in order of appearance'],
            command=lambda: self.change_sort(change=True),
            compound=CENTER,
            style='New2.TButton')
        self.change_sort(self.sort_mode)
        self.change_sort_button.place(x=0, y=320, width=300, height=30)
        self.frame_show.place(x=600, y=370, width=300, height=70)
        self.current_widgets = [
            self.go_back_button, self.config_options_bar,
            self.choose_config_options, self.config_contents,
            self.choose_filename_button, self.choose_directory_button,
            self.save_button, self.search_text, self.search_entry,
            self.up_button, self.down_button, self.choose_bool1,
            self.choose_bool2, self.change_sort_button, self.config_name,
            self.frame_show
        ]
        self.frame_info.set(translate_dict['No actions at this time'])
        self.choose_config_options.selection_set(0)
        self.choose_config_options.selection_anchor(0)
        self.show_current_config_options(0)

    def change_sort(self, mode=0, change=False):
        if change:
            mode = 1 - self.sort_mode
        if mode == 1:
            self.sort_mode = 1
            self.change_sort_button.config(
                text=translate_dict['Sort in order of appearance'])
            self.all_config_options = self.config_original.copy()
            self.translate_all_config_options = [
                translate_dict[i] for i in self.all_config_options
            ]
            self.choose_config_options.delete(0, END)
            for k in self.all_config_options:
                self.choose_config_options.insert(END, translate_dict[k])
        else:
            self.sort_mode = 0
            self.change_sort_button.config(
                text=translate_dict['Sort in alphabetical order'])
            self.all_config_options = self.alpha_config.copy()
            self.translate_all_config_options = [
                translate_dict[i] for i in self.all_config_options
            ]
            self.choose_config_options.delete(0, END)
            for k in self.all_config_options:
                self.choose_config_options.insert(END, translate_dict[k])
        if not self.search_contents.get():
            self.choose_config_options.selection_set(0)
        else:
            self.search()

    def insert_bool(self, content):
        self.config_contents.delete('1.0', END)
        self.config_contents.insert(END, content)
        self.config_change(0)

    def config_change(self, e):
        current_config = self.choose_config_options.get(ANCHOR)
        try:
            current = self.config_contents.get('1.0', 'end-1c')
            self.value_dict[
                translate_dict_reverse[current_config]] = get_value(current)
        except Exception as e:
            print(str(e))

    def change_search_inds(self, num):
        self.search_inds += num
        if self.search_inds < 0:
            self.search_inds = 0
        if self.search_inds_list:
            search_num = len(self.search_inds_list)
            if self.search_inds >= search_num:
                self.search_inds = search_num - 1
            first = self.search_inds_list[self.search_inds]
            self.choose_config_options.selection_clear(0, END)
            self.choose_config_options.selection_set(first)
            self.choose_config_options.selection_anchor(first)
            self.choose_config_options.see(first)
            self.show_current_config_options(0)

    def search(self, *args):
        current = self.search_contents.get()
        if not current:
            return
        self.search_inds_list = [
            i for i in range(self.options_num)
            if current in self.translate_all_config_options[i]
        ]
        if self.search_inds_list:
            self.search_inds = 0
            first = self.search_inds_list[self.search_inds]
            self.choose_config_options.selection_clear(0, END)
            self.choose_config_options.selection_set(first)
            self.choose_config_options.selection_anchor(first)
            self.choose_config_options.see(first)
            self.show_current_config_options(0)
        else:
            self.choose_config_options.selection_clear(0, END)

    def show_current_config_options(self, e):
        if not self.already_place_config_name:
            self.already_place_config_name = True
            self.config_name.place(x=400, y=100, height=35)
        current_config = self.choose_config_options.get(ANCHOR)
        if current_config:
            self.config_name.configure(text=current_config)
            self.config_contents.delete('1.0', END)
            real_key = translate_dict_reverse.get(current_config, current_config)
            if hasattr(self, 'choose_bool1') and hasattr(self, 'choose_bool2'):
                if real_key == 'language':
                    self.choose_bool1.configure(text='中文 (Chinese)', command=lambda: self.insert_bool('Chinese'))
                    self.choose_bool2.configure(text='English (英文)', command=lambda: self.insert_bool('English'))
                else:
                    self.choose_bool1.configure(text='True', command=lambda: self.insert_bool('True'))
                    self.choose_bool2.configure(text='False', command=lambda: self.insert_bool('False'))
            current_config_value = self.value_dict.get(real_key, '')
            if type(current_config_value) == list:
                current_config_value = current_config_value[1]
            current_config_value = get_value(current_config_value)
            self.config_contents.insert(END, str(current_config_value))

    def choose_filename(self):
        filename = filedialog.askopenfilename(
            title=translate_dict['Choose filename'],
            filetypes=((translate_dict['All files'], "*"), ))
        if not filename:
            return
        self.config_contents.delete('1.0', END)
        self.config_contents.insert(END, filename)
        self.config_change(0)

    def choose_directory(self):
        directory = filedialog.askdirectory(
            title=translate_dict['Choose directory'])
        if not directory:
            return
        self.config_contents.delete('1.0', END)
        self.config_contents.insert(END, directory)
        self.config_change(0)

    def insert_value(self, value):
        if value == 1:
            value = 'True'
        elif value == 0:
            value = 'False'
        current_focus = self.focus_get()
        if 'text' in str(current_focus):
            current_focus.delete('1.0', END)
            current_focus.insert(END, value)

    def save_current_contents(self, current_entry, real_value):
        try:
            current = current_entry.get('1.0', 'end-1c')
            self.value_dict[real_value] = get_value(current)
        except Exception as e:
            print(str(e))

    def search_path(self, obj, mode=0):
        current_filename = obj.get('1.0', 'end-1c')
        if os.path.isfile(current_filename):
            current_directory = os.path.dirname(current_filename)
        elif os.path.isdir(current_filename):
            current_directory = current_filename
        else:
            current_directory = ''
        if mode == 0:
            filename = filedialog.askopenfilename(
                initialdir=current_directory,
                title=translate_dict['Choose filename'],
                filetypes=((translate_dict['All files'], "*"), ))
        elif mode == 1:
            filename = filedialog.askdirectory(
                initialdir=current_directory,
                title=translate_dict['Choose directory'])
        if filename:
            obj.delete('1.0', END)
            obj.insert(END, filename)
            obj.func(1)

    def show_saved(self):
        self.frame_info.set(translate_dict['Current settings are saved'])

    def save_current(self):
        changed = False
        changed_values = []
        for each in self.value_dict:
            if each not in self.value_entry_dict:
                before_value = current_settings[each]
                current_value = self.value_dict[each]
                if not isinstance(before_value, str):
                    if current_value in ['', 'None']:
                        current_value = None
                    else:
                        current_value = get_value(current_value)
                if current_value != before_value:
                    change(each, current_value)
                    changed = True
                    changed_values.append(each)
                    current_settings[each] = current_value
            else:
                current_button = self.value_entry_dict[each]
                if isinstance(current_button, ttk.Checkbutton):
                    current_value = current_button.var.get()
                    current_value = True if current_value else False
                    before_value = current_settings[each]
                    if current_value != before_value:
                        change(each, current_value)
                        changed = True
                        changed_values.append(each)
                        current_settings[each] = current_value
                else:
                    current_value = current_button.get('1.0', 'end-1c')
                    before_value = current_settings[each]
                    if not isinstance(before_value, str):
                        if current_value in ['', 'None']:
                            current_value = None
                        else:
                            current_value = get_value(current_value)
                    if current_value != before_value:
                        change(each, current_value)
                        changed = True
                        changed_values.append(each)
                        current_settings[each] = current_value
        if changed:
            if 'language' in changed_values:
                raw_lang = self.value_dict.get('language', 'Chinese')
                new_lang = normalize_language(raw_lang)
                self.apply_language(new_lang)
            if 'background_image' in changed_values:
                try:
                    bg_image = Image.open(background_image)
                except:
                    bg_image = Image.open('resources/background.png')
                self.background_image = ImageTk.PhotoImage(
                    bg_image.resize(
                        (1000,
                         int(1000 * (bg_image.height / bg_image.width)))))
                self.bg_label.configure(image=self.background_image)
            self.show_saved()
        else:
            self.frame_info.set(
                translate_dict['There\'s no changes in current settings'])

    def toggle_language(self):
        cur = normalize_language(self.value_dict.get('language', 'Chinese'))
        new_lang = 'English' if cur == 'Chinese' else 'Chinese'
        self.apply_language(new_lang)

    def apply_language(self, new_lang):
        new_lang = normalize_language(new_lang)
        self.value_dict['language'] = new_lang
        current_settings['language'] = new_lang
        change('language', new_lang)
        global translate_dict, translate_dict_reverse
        try:
            with open(f'scripts/languages/{new_lang}.json', encoding='utf-8') as f:
                translate_dict = json.load(f)
        except:
            with open('scripts/languages/English.json', encoding='utf-8') as f:
                translate_dict = json.load(f)
        translate_dict_reverse = {j: i for i, j in translate_dict.items()}
        self.set_style()
        self.translate_all_config_options = [
            translate_dict.get(i, i) for i in self.all_config_options
        ]
        if hasattr(self, 'save_button') and self.save_button.winfo_exists():
            self.save_button.configure(text=translate_dict.get('Save Current Settings', 'Save'))
        if hasattr(self, 'go_back_button') and self.go_back_button.winfo_exists():
            self.go_back_button.configure(text=translate_dict.get('Back', 'Back'))
        if hasattr(self, 'search_text') and self.search_text.winfo_exists():
            self.search_text.configure(text=translate_dict.get('Search Settings', 'Search'))
        if hasattr(self, 'up_button') and self.up_button.winfo_exists():
            self.up_button.configure(text=translate_dict.get('Previous', 'Prev'))
        if hasattr(self, 'down_button') and self.down_button.winfo_exists():
            self.down_button.configure(text=translate_dict.get('Next', 'Next'))
        if hasattr(self, 'choose_filename_button') and self.choose_filename_button.winfo_exists():
            self.choose_filename_button.configure(text=translate_dict.get('Choose filename', 'Choose File'))
        if hasattr(self, 'choose_directory_button') and self.choose_directory_button.winfo_exists():
            self.choose_directory_button.configure(text=translate_dict.get('Choose directory', 'Choose Dir'))
        if hasattr(self, 'change_sort_button') and self.change_sort_button.winfo_exists():
            sort_txt = translate_dict['Sort in order of appearance'] if self.sort_mode == 1 else translate_dict['Sort in alphabetical order']
            self.change_sort_button.configure(text=sort_txt)
        if hasattr(self, 'choose_config_options') and self.choose_config_options.winfo_exists():
            cur_idx = self.choose_config_options.curselection()
            idx = cur_idx[0] if cur_idx else 0
            self.choose_config_options.delete(0, END)
            for k in self.all_config_options:
                self.choose_config_options.insert(END, translate_dict.get(k, k))
            self.choose_config_options.selection_set(idx)
            self.choose_config_options.selection_anchor(idx)
            self.show_current_config_options(0)
        if hasattr(self, 'toggle_language_button') and self.toggle_language_button.winfo_exists():
            lang_text = "🌐 切换为 English" if self.value_dict.get('language') == 'Chinese' else "🌐 切换为 中文"
            self.toggle_language_button.configure(text=lang_text)
        if hasattr(self, 'img_to_ascii_img_button') and self.img_to_ascii_img_button.winfo_ismapped():
            self.reset_main_window()

    def quit_main_window(self):
        for w in self.main_widgets:
            w.place_forget()

    def reset_main_window(self):
        self.set_style()
        self.html_button.place(x=520, y=340, width=450, height=60)
        self.img_to_ascii_img_button.configure(text=translate_dict['Image to Ascii Images/Texts'])
        self.img_to_ascii_img_button.place(x=0, y=140, width=500, height=60)
        self.video_to_ascii_video_button.configure(text=translate_dict['Videos to Ascii Videos'])
        self.video_to_ascii_video_button.place(x=0, y=240, width=500, height=60)
        self.video_to_ascii_img_button.configure(text=translate_dict['Extract Frames From Videos'])
        self.video_to_ascii_img_button.place(x=0, y=340, width=500, height=60)
        self.change_settings_button.configure(text=translate_dict['Change Settings'])
        self.change_settings_button.place(x=0, y=440, width=500, height=60)
        lang_text = "🌐 切换为 English" if self.value_dict.get('language') == 'Chinese' else "🌐 切换为 中文"
        self.toggle_language_button.configure(text=lang_text)
        self.toggle_language_button.place(x=0, y=520, width=500, height=55)

    def go_back_main_window(self):
        preview = getattr(self, '_ascii_preview', None)
        if preview is not None and preview.winfo_exists():
            preview.close()
        os.chdir(abs_path)
        self.go_back = True
        for i in self.current_widgets:
            i.place_forget()
        self.reset_main_window()
        self.var_counter = 1

    def get_char(self, r, g, b, alpha=None):
        if alpha == 0:
            return " "
        elif alpha is None:
            alpha = self.K
        gray = int(0.2126 * r + 0.7152 * g + 0.0722 * b)
        return self.value_dict['ascii_character_set'][int(gray / self.unit)]

    def img_to_ascii(self, im, show_percentage=False, mode=0):
        WIDTH = int((im.width / self.font_x_len) *
                    self.value_dict['image_width_ratio'] /
                    self.value_dict['resize_ratio'])
        HEIGHT = int((im.height / self.font_y_len) *
                     self.value_dict['image_height_ratio'] /
                     self.value_dict['resize_ratio'])
        if show_percentage:
            whole_count = WIDTH * HEIGHT
            count = 0
        im_resize = im.resize((WIDTH, HEIGHT), getattr(Image, 'LANCZOS', getattr(Image, 'ANTIALIAS', 1)))
        txt = ""
        if mode == 1:
            im_txt = Image.new(
                self.value_dict['colored_ascii_image_mode'],
                (int(im.width / self.value_dict['resize_ratio']),
                 int(im.height / self.value_dict['resize_ratio'])),
                (2**self.value_dict['bit_number'] - 1,
                 2**self.value_dict['bit_number'] - 1,
                 2**self.value_dict['bit_number'] - 1))
            colors = []
            for i in range(HEIGHT):
                for j in range(WIDTH):
                    pixel = im_resize.getpixel((j, i))
                    colors.append(pixel)
                    txt += self.get_char(*pixel)
                if show_percentage:
                    count += WIDTH
                    self.frame_info.set(
                        f'{translate_dict["Conversion progress:"]}  {round((count/whole_count)*100, 3)}%'
                    )
                    self.update()
                txt += '\n'
                colors.append((255, 255, 255))
            return txt, colors, im_txt
        else:
            for i in range(HEIGHT):
                for j in range(WIDTH):
                    pixel = im_resize.getpixel((j, i))
                    txt += self.get_char(*pixel)
                if show_percentage:
                    count += WIDTH
                    self.frame_info.set(
                        f'{translate_dict["Conversion progress:"]}  {round((count/whole_count)*100, 3)}%'
                    )
                    self.update()
                txt += '\n'
            return txt

    def image_to_ascii_text(self):
        self.frame_info.set(translate_dict['Converting images..'])
        self.update()
        self.reinit()
        if not self.value_dict['image_path'] or not os.path.isfile(
                self.value_dict['image_path']):
            self.frame_info.set(
                translate_dict['This image path does not exist'])
            return
        try:
            im = Image.open(self.value_dict['image_path'])
            text_str_output = self.img_to_ascii(
                im, self.value_dict['show_convert_percentages'])
            if type(text_str_output) != str:
                text_str = text_str_output[0]
            else:
                text_str = text_str_output
        except Exception as e:
            print(str(e))
            self.frame_info.set(
                translate_dict['This image path does not exist'])
            self.update()
            return
        file_name = os.path.splitext(
            os.path.basename(self.value_dict['image_path']))[0]
        self.frame_info.set(translate_dict[
            'Converting images are finished, writing ascii result to text...'])
        self.update()
        output_filename = filedialog.asksaveasfilename(
            initialfile=f'ascii_{file_name}.txt',
            title=translate_dict[
                'Choose the file path of the exported ASCII text file'],
            filetypes=((translate_dict['All files'], "*"), ))
        if not output_filename:
            self.frame_info.set(translate_dict['canceled exporting'])
            return
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(text_str)
        self.frame_info.set(
            translate_dict['Successfully writing to text file'])
        self.update()

    def image_to_ascii_image(self):
        self.frame_info.set(translate_dict['Converting images..'])
        self.update()
        self.reinit()
        if not self.value_dict['image_path'] or not os.path.isfile(
                self.value_dict['image_path']):
            self.frame_info.set(
                translate_dict['This image path does not exist'])
            return
        try:
            im = Image.open(self.value_dict['image_path'])
            text_str_output = self.img_to_ascii(
                im,
                self.value_dict['show_convert_percentages'],
                mode=self.is_color)
            if type(text_str_output) != str:
                text_str = text_str_output[0]
            else:
                text_str = text_str_output
        except Exception as e:
            print(str(e))
            self.frame_info.set(
                translate_dict['This image path does not exist'])
            self.update()
            return
        file_name = os.path.splitext(
            os.path.basename(self.value_dict['image_path']))[0]
        self.frame_info.set(translate_dict[
            'Converting images are finished, writing ascii result to image...']
                            )
        self.update()
        output_filename = filedialog.asksaveasfilename(
            initialfile=f'ascii_{file_name}.png',
            title=translate_dict[
                'Choose the file path of the exported ASCII image file'],
            filetypes=((translate_dict['All files'], "*"), ))
        if not output_filename:
            self.frame_info.set(translate_dict['canceled exporting'])
            return
        if self.is_color == 0:
            im_txt = Image.new(
                self.value_dict['ascii_image_mode'],
                (int(im.width / self.value_dict['resize_ratio']),
                 int(im.height / self.value_dict['resize_ratio'])),
                self.value_dict['ascii_image_init_bg_color'])
            dr = ImageDraw.Draw(im_txt)
            x = y = 0
            ascii_image_character_color = self.value_dict[
                'ascii_image_character_color']
            for i in range(len(text_str)):
                if text_str[i] == "\n":
                    x = 0
                    y += self.font_y_len
                dr.text((x, y),
                        text_str[i],
                        fill=ascii_image_character_color,
                        font=self.font)
                x += self.font_x_len
            im_txt.save(output_filename)

        else:
            txt, colors, im_txt = text_str_output
            dr = ImageDraw.Draw(im_txt)
            x = y = 0
            for i in range(len(txt)):
                if txt[i] == "\n":
                    x = 0
                    y += self.font_y_len
                dr.text((x, y), txt[i], fill=colors[i], font=self.font)
                x += self.font_x_len
            im_txt.save(output_filename)

        self.frame_info.set(
            translate_dict['Successfully writing to image file'])
        self.update()

    def video_to_ascii_video(self, mode=0):
        self.reinit()
        video_frames_path = None
        if mode == 1:
            video_frames_path = filedialog.askdirectory(
                title=translate_dict['Choose video frames path'])
            if not video_frames_path:
                return
        if video_frames_path:
            os.chdir(video_frames_path)
            file_ls = [f for f in os.listdir() if os.path.isfile(f)]
            file_ls.sort(key=lambda x: int(os.path.splitext(x)[0]))
            file_ls = [
                os.path.normpath(os.path.join(os.sep, video_frames_path, i))
                for i in file_ls
            ]
            frames = (Image.open(i) for i in file_ls)
            start_frame = 0
            frame_length = len(file_ls)
        else:
            if not self.value_dict['video_path'] or not os.path.isfile(
                    self.value_dict['video_path']):
                self.frame_info.set(
                    translate_dict['This video path does not exist'])
                return
            vidcap = cv2.VideoCapture(self.value_dict['video_path'])
            count = 0
            start_frame = 0
            if not self.value_dict['video_frames_interval']:
                whole_frame_number = int(vidcap.get(cv2.CAP_PROP_FRAME_COUNT))
                frames = (Image.fromarray(
                    cv2.cvtColor(vidcap.read()[1], cv2.COLOR_BGR2RGB))
                          for k in range(whole_frame_number))
                frame_length = whole_frame_number
            else:
                start_frame, to_frame = self.value_dict[
                    'video_frames_interval']
                no_of_frames = to_frame - start_frame
                frame_length = no_of_frames
                vidcap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
                frames = (Image.fromarray(
                    cv2.cvtColor(vidcap.read()[1], cv2.COLOR_BGR2RGB))
                          for k in range(no_of_frames))
        if video_frames_path:
            file_name = os.path.splitext(
                os.path.basename(video_frames_path))[0]
        else:
            file_name = os.path.splitext(
                os.path.basename(self.value_dict['video_path']))[0]
        output_filename = filedialog.asksaveasfilename(
            initialfile=f'ascii_{file_name}.mp4',
            title=translate_dict['Choose the file path of the exported video'],
            filetypes=((translate_dict['All files'], "*"), ))
        if not output_filename:
            self.frame_info.set(translate_dict['canceled exporting'])
            return
        if video_frames_path:
            os.chdir(abs_path)
        if not os.path.exists('temp_video_images'):
            os.mkdir('temp_video_images')
        os.chdir('temp_video_images')
        for each in os.listdir():
            os.remove(each)
        num_frames = frame_length
        n = len(str(num_frames))
        if self.is_color == 0:
            for i in range(num_frames):
                if self.go_back:
                    break
                self.frame_info.set(
                    translate_dict['Converting video frame'].format(
                        start_frame + i + 1, start_frame + num_frames))
                self.update()
                try:
                    im = next(frames)
                except:
                    break
                text_str = self.img_to_ascii(im)
                im_txt = Image.new(
                    self.value_dict['ascii_image_mode'],
                    (int(im.width / self.value_dict['resize_ratio']),
                     int(im.height / self.value_dict['resize_ratio'])),
                    self.value_dict['ascii_image_init_bg_color'])
                dr = ImageDraw.Draw(im_txt)
                x = y = 0
                ascii_image_character_color = self.value_dict[
                    'ascii_image_character_color']
                for j in range(len(text_str)):
                    if text_str[j] == "\n":
                        x = 0
                        y += self.font_y_len
                    dr.text((x, y),
                            text_str[j],
                            fill=ascii_image_character_color,
                            font=self.font)
                    x += self.font_x_len
                if self.go_back:
                    break
                im_txt.save(f'{i:0{n}d}.png')
        else:
            for i in range(num_frames):
                if self.go_back:
                    break
                self.frame_info.set(
                    translate_dict['Converting video frame'].format(
                        start_frame + i + 1, start_frame + num_frames))
                self.update()
                try:
                    text_str_output = self.img_to_ascii(next(frames),
                                                        mode=self.is_color)
                except:
                    break
                txt, colors, im_txt = text_str_output
                dr = ImageDraw.Draw(im_txt)
                x = y = 0
                for j in range(len(txt)):
                    if txt[j] == "\n":
                        x = 0
                        y += self.font_y_len
                    dr.text((x, y), txt[j], fill=colors[j], font=self.font)
                    x += self.font_x_len
                if self.go_back:
                    break
                im_txt.save(f'{i:0{n}d}.png')
        self.frame_info.set(
            translate_dict['Conversion are finished, start to export video..'])
        self.update()
        os.chdir(abs_path)
        if self.go_back:
            return
        current_framerate = self.value_dict['video_frame_rate']
        if not current_framerate:
            current_framerate = vidcap.get(cv2.CAP_PROP_FPS)
        ffmpeg.input(f'temp_video_images/%{n}d.png',
                     framerate=current_framerate).output(
                         output_filename,
                         pix_fmt='yuv420p').run(overwrite_output=True)
        self.frame_info.set(
            translate_dict['Video has been successfully exported'])
        self.update()

    def video_to_img(self):
        self.reinit()
        if not self.value_dict['video_path'] or not os.path.isfile(
                self.value_dict['video_path']):
            self.frame_info.set(
                translate_dict['This video path does not exist'])
            return
        video_frames_save_path = filedialog.askdirectory(
            title=translate_dict['Choose the path to save video frames'])
        if not video_frames_save_path:
            return
        try:
            os.chdir(video_frames_save_path)
        except:
            if not os.path.exists('video_frame_ascii_images'):
                os.mkdir('video_frame_ascii_images')
            os.chdir('video_frame_ascii_images')
            for each in os.listdir():
                os.remove(each)
        vidcap = cv2.VideoCapture(self.value_dict['video_path'])
        count = 0
        start_frame = 0
        if not self.value_dict['video_frames_interval']:
            whole_frame_number = int(vidcap.get(cv2.CAP_PROP_FRAME_COUNT))
            num_frames = whole_frame_number
            frames = (Image.fromarray(
                cv2.cvtColor(vidcap.read()[1], cv2.COLOR_BGR2RGB))
                      for k in range(whole_frame_number))
            is_read, img = vidcap.read()
            while is_read:
                if self.go_back:
                    break
                cv2.imwrite(f"{count}.png", img)
                is_read, img = vidcap.read()
                count += 1
                self.frame_info.set(
                    f'{translate_dict["Reading and exporting video frame"]} {count}/{start_frame + num_frames}'
                )
                self.update()
            vidcap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        else:
            start_frame, to_frame = self.value_dict['video_frames_interval']
            no_of_frames = to_frame - start_frame
            num_frames = no_of_frames
            vidcap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            frames = (Image.fromarray(
                cv2.cvtColor(vidcap.read()[1], cv2.COLOR_BGR2RGB))
                      for k in range(no_of_frames))
            is_read, img = vidcap.read()
            for k in range(no_of_frames):
                if self.go_back:
                    break
                if is_read:
                    cv2.imwrite(f"{count}.png", img)
                    is_read, img = vidcap.read()
                    count += 1
                    self.frame_info.set(
                        f'{translate_dict["Reading and exporting video frame"]} {start_frame + count}/{start_frame + num_frames}'
                    )
                    self.update()
                else:
                    break
            vidcap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        os.chdir(abs_path)
        self.frame_info.set(
            translate_dict['Video frames are successfully exported as images'])
        self.update()
        return

    def reinit(self):
        self.is_color = self.picture_color.get()
        length = len(self.value_dict['ascii_character_set'])
        self.K = 2**self.value_dict['bit_number']
        self.unit = (self.K + 1) / length

    def set_value(self,
                  value_name,
                  real_value,
                  width,
                  height,
                  x1,
                  y1,
                  path_enable=False,
                  path_mode=0,
                  mode=0,
                  font_size=12):
        current_widgets = []
        if mode == 0:
            value_label = ttk.Label(self, text=translate_dict[real_value])
            value_label.place(x=x1, y=y1, width=width, height=25)
            value_entry = Text(self,
                               undo=True,
                               autoseparators=True,
                               maxundo=-1,
                               background='white',
                               foreground='black',
                               insertbackground='black')
            before_value = self.value_dict[real_value]
            before_value = str(before_value)
            if before_value == 'None':
                before_value = ''
            value_entry.insert(END, before_value)
            value_entry.configure(font=(self.current_font, 12))
            value_entry.place(x=x1, y=y1 + 25, width=width, height=height)
            self.value_entry_dict[real_value] = value_entry
            current_widgets.append(value_label)
            current_widgets.append(value_entry)
            value_entry.func = lambda e: self.save_current_contents(
                value_entry, real_value)
            value_entry.bind('<KeyRelease>', value_entry.func)
        elif mode == 1:
            exec(f"self.checkvar{self.var_counter} = IntVar()")
            checkvar = eval(f"self.checkvar{self.var_counter}")
            self.var_counter += 1
            before_value = self.value_dict[real_value]
            if type(before_value) == list:
                before_value = before_value[1]
            checkvar.set(1 if before_value else 0)
            value_checkbutton = ttk.Checkbutton(
                self,
                text=translate_dict[real_value],
                variable=checkvar,
                command=lambda: self.change_bool(real_value))
            value_checkbutton.var = checkvar
            self.value_entry_dict[real_value] = value_checkbutton
            value_checkbutton.place(x=x1, y=y1, width=width, height=height)
            current_widgets.append(value_checkbutton)
        if path_enable:
            path_button = ttk.Button(
                self,
                text=translate_dict['change'],
                command=lambda: self.search_path(value_entry, path_mode),
                compound=CENTER,
                style='New.TButton')
            path_button.place(x=x1 + width + 15,
                              y=y1 + 5,
                              width=200,
                              height=50)
            current_widgets.append(path_button)
        return current_widgets

    def change_bool(self, value_name):
        self.value_dict[value_name] = not self.value_dict[value_name]


root = Root()
root.mainloop()
