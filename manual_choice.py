import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from models import *
from models import db
import re
import math
import time   # в начале файла
# ========== ДИАЛОГ ВЫБОРА ДЕЙСТВИЯ ==========
class ChoiceActionDialog(QDialog):
    def __init__(self, parent=None):

        self._last_placed = None   # (g_idx, row, timestamp)

        super().__init__(parent)
        self.setWindowTitle("Жеребьевка спортсменов")
        self.setModal(True)
        self.setFixedSize(450, 220)

        
        layout = QVBoxLayout(self)
        
        title_label = QLabel("Жеребьевка спортсменов")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        info_label = QLabel("В базе данных уже есть результаты жеребьевки.\n\nВыберите действие:")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        button_layout = QHBoxLayout()
        
        self.btn_reset = QPushButton("Сбросить")
        self.btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        self.btn_reset.clicked.connect(lambda: self.done(1))
        button_layout.addWidget(self.btn_reset)
        
        self.btn_load = QPushButton("Загрузить")
        self.btn_load.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.btn_load.clicked.connect(lambda: self.done(2))
        button_layout.addWidget(self.btn_load)
        
        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        self.btn_cancel.clicked.connect(lambda: self.done(0))
        button_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(button_layout)
        
        info_text = QLabel("• Сбросить - начать новую жеребьевку\n• Загрузить - продолжить редактирование существующей\n• Отмена - выйти без изменений")
        info_text.setStyleSheet("color: #666; font-size: 11px; margin-top: 10px;")
        info_text.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_text)

# ========== ОСНОВНОЙ КЛАСС ЖЕРЕБЬЕВКИ ==========
class ChoiceGroupManual(QDialog):
    def __init__(self, athletes, num_groups, id_title, sex, parent=None, existing_data=None):
        super().__init__(parent)
        self.athletes = athletes
        self.sorted_athletes = []
        self.groups = []
        self.num_groups = num_groups
        self.current_athlete_index = 0
        self.group_tables = []
        self.group_headers = []
        self.current_group_for_seed = None
        self.current_round = 1
        self.max_rows_per_group = 0
        self.existing_data = existing_data
        self.sex = sex
        self.initUI()
# ========= new
        # F11 — переключение полного экрана
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)
        # Esc — выход из полного экрана (по желанию)
        QShortcut(QKeySequence("Esc"), self, activated=self._on_escape)
# ==============
        self.load_athletes()
        self.calculate_max_rows()
        self.init_groups()
        #=======new
        self.is_fullscreen = False          # <-- NEW
        self._saved_geometry = None         # <-- NEW
        #=================
        if self.existing_data:
            self.load_existing_draw()
        else:
            self.calculate_initial_group()
        
        self.setModal(True)


# ========= new
    def _on_escape(self):
        """Esc: если в fullscreen — выходим из него, иначе — закрываем диалог."""
        if self.is_fullscreen:
            self.toggle_fullscreen()
        else:
            self.reject()
# ========= 
    def load_existing_draw(self):
        """Загрузка существующей жеребьевки из базы данных"""
        # Инициализируем группы
        self.groups = [[] for _ in range(self.num_groups)]

        # Заполняем группы данными из базы
        for item in self.existing_data:
            player_id = item.player_choice_id
            mark = item.group.find(" ")
            gr_num = int(item.group[:mark])
            group_num = gr_num - 1
            position = item.posev_group - 1
            
            # Находим спортсмена по id
            athlete = None
            for a in self.athletes:
                if a[0] == player_id:
                    athlete = a
                    break
            
            if athlete and group_num < self.num_groups:
                while len(self.groups[group_num]) <= position:
                    self.groups[group_num].append(None)
                self.groups[group_num][position] = athlete
                
                if athlete in self.sorted_athletes:
                    idx = self.sorted_athletes.index(athlete)
                    if idx >= self.current_athlete_index:
                        self.sorted_athletes.pop(idx)
        
        placed_count = sum(1 for group in self.groups for athlete in group if athlete)
        self.current_athlete_index = placed_count
        self.update_round_display()
        self.update_groups_display()
        self.highlight_current_group()
        
        if self.current_athlete_index >= len(self.athletes):
            QMessageBox.information(self, "Информация", "Жеребьевка уже завершена! Все спортсмены распределены.")
        
    def calculate_initial_group(self):
        """Определение начальной группы для посева"""
        if self.num_groups > 0:
            self.current_group_for_seed = self.num_groups - 1
            
    def calculate_max_rows(self):
        """Расчет максимального количества строк в группе"""
        total_athletes = len(self.athletes)
        self.max_rows_per_group = (total_athletes + self.num_groups - 1) // self.num_groups
        if self.max_rows_per_group < 1:
            self.max_rows_per_group = 1
            
    def get_current_round(self):
        """Определение текущего раунда на основе количества размещенных спортсменов"""
        placed_count = self.current_athlete_index
        
        if placed_count == 0:
            return 1
        
        if placed_count <= self.num_groups:
            return 1
        else:
            round_num = (placed_count - 1) // self.num_groups + 1
            return round_num
    
    def update_round_display(self):
        """Обновление отображения текущего раунда"""
        self.current_round = self.get_current_round()
        direction = "→" if self.current_round % 2 == 1 else "←"
        self.round_label.setText(f"Круг: {self.current_round}\nНаправление: {direction}")

    def initUI(self):
        self.setWindowTitle('Ручная жеребьевка спортсменов')
        # Стартовый размер — не фиксируем максимум, чтобы работал fullscreen
        self.resize(1600, 850)
        self.setMinimumSize(1100, 700)
        self.setMaximumSize(3840, 2160)   # 4K — с запасом
#===============  
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(5)  # Уменьшаем отступы
        main_layout.setContentsMargins(5, 5, 5, 5)  # Уменьшаем отступы
        
        title_label = QLabel("Ручная жеребьевка спортсменов")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin: 5px;")  # Уменьшен margin
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        content_layout = QHBoxLayout()
        content_layout.setSpacing(5)  # Уменьшаем отступ между панелями
        
        # ========== ЛЕВАЯ ПАНЕЛЬ ==========
        left_panel = QFrame()
        left_panel.setFrameStyle(QFrame.StyledPanel)
        left_panel.setMaximumWidth(300)  # Уменьшено с 330
        left_panel.setMinimumWidth(280)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(3)  # Уменьшаем отступы
        left_layout.setContentsMargins(3, 3, 3, 3)
        
        # Горизонтальный layout для информации
        info_layout = QHBoxLayout()
        info_layout.setSpacing(3)
        
        # Информация о текущем спортсмене
        current_athlete_group = QGroupBox("Текущий спортсмен")
        current_athlete_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 11px; }")
        current_athlete_layout = QVBoxLayout(current_athlete_group)
        current_athlete_layout.setSpacing(2)
        
        self.current_athlete_label = QLabel("Спортсмен: -\nРейтинг: -\nРегион: -\nТренер: -")
        self.current_athlete_label.setStyleSheet("background-color: #ffe0b3; padding: 5px; font-size: 10px;")
        self.current_athlete_label.setWordWrap(True)
        current_athlete_layout.addWidget(self.current_athlete_label)
        
        left_layout.addWidget(current_athlete_group)
        
        # Информация о текущей группе
        current_group_group = QGroupBox("Текущая группа")
        current_group_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 11px; }")
        current_group_layout = QVBoxLayout(current_group_group)
        current_group_layout.setSpacing(2)
        
        self.current_group_label = QLabel("Группа: -\nИгроков: -")
        self.current_group_label.setStyleSheet("background-color: #b3d9ff; padding: 5px; font-size: 10px;")
        current_group_layout.addWidget(self.current_group_label)
        
        info_layout.addWidget(current_group_group)
        
        # Информация о текущем круге
        round_group = QGroupBox("Текущий круг")
        round_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 11px; }")
        round_layout = QVBoxLayout(round_group)
        round_layout.setSpacing(2)
        
        self.round_label = QLabel("Круг: 1\nНаправление: →")
        self.round_label.setStyleSheet("background-color: #d4e6f1; padding: 5px; font-size: 10px;")
        round_layout.addWidget(self.round_label)
        
        info_layout.addWidget(round_group)
        
        left_layout.addLayout(info_layout)
        
        # Список участников
        athletes_group = QGroupBox("Список участников")
        athletes_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 11px; }")
        athletes_layout = QVBoxLayout(athletes_group)
        athletes_layout.setSpacing(2)
        
        self.athletes_table = QTableWidget()
        self.athletes_table.setColumnCount(4)
        self.athletes_table.setHorizontalHeaderLabels(["ID", "ФИО", "Рейтинг", "Регион"])
        self.athletes_table.horizontalHeader().setStretchLastSection(True)
        self.athletes_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.athletes_table.setAlternatingRowColors(True)
        self.athletes_table.verticalHeader().setDefaultSectionSize(20)  # Уменьшаем высоту строк
        athletes_layout.addWidget(self.athletes_table)
        
        left_layout.addWidget(athletes_group)
        
        # Статистика и управление
        control_group = QGroupBox("Управление")
        control_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 11px; }")
        control_layout = QVBoxLayout(control_group)
        control_layout.setSpacing(3)
        
        # Статистика
        stats_layout = QGridLayout()
        stats_layout.addWidget(QLabel("Всего спортсменов:"), 0, 0)
        self.total_label = QLabel("0")
        stats_layout.addWidget(self.total_label, 0, 1)
        stats_layout.addWidget(QLabel("Размещено:"), 1, 0)
        self.placed_label = QLabel("0")
        stats_layout.addWidget(self.placed_label, 1, 1)
        stats_layout.addWidget(QLabel("Осталось:"), 2, 0)
        self.remaining_label = QLabel("0")
        stats_layout.addWidget(self.remaining_label, 2, 1)
        stats_layout.addWidget(QLabel("Макс. в группе:"), 3, 0)
        self.max_rows_label = QLabel("0")
        stats_layout.addWidget(self.max_rows_label, 3, 1)
        stats_layout.addWidget(QLabel("Текущий круг:"), 4, 0)
        self.round_number_label = QLabel("1")
        stats_layout.addWidget(self.round_number_label, 4, 1)
        control_layout.addLayout(stats_layout)
        
        # Кнопки управления
        btn_layout = QGridLayout()
        btn_layout.setSpacing(2)

        self.btn_reset = QPushButton("Сбросить")
        self.btn_reset.setFixedHeight(25)  # Фиксированная высота
        self.btn_reset.clicked.connect(self.reset_draw)
        btn_layout.addWidget(self.btn_reset, 0, 0, 1, 1)
        
        self.btn_auto = QPushButton("Авто (1 номера)")
        self.btn_auto.setFixedHeight(25)
        self.btn_auto.clicked.connect(self.auto_fill_first)
        btn_layout.addWidget(self.btn_auto, 1, 0, 1, 1)
        
        self.btn_clear = QPushButton("Очистить")
        self.btn_clear.setFixedHeight(25)
        self.btn_clear.clicked.connect(self.clear_all_groups)
        btn_layout.addWidget(self.btn_clear, 0, 1, 1, 1)

        self.btn_edit = QPushButton("Редактор")
        self.btn_edit.setFixedHeight(25)
        self.btn_edit.clicked.connect(self.open_editor)
        self.btn_edit.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold;")
        # self.btn_edit.setEnabled(False)
        btn_layout.addWidget(self.btn_edit, 1, 1, 1, 1)
# ============ new
        # --- NEW: кнопка полного экрана ---
        self.btn_fullscreen = QPushButton("⛶ Полный экран (F11)")
        self.btn_fullscreen.setFixedHeight(25)
        self.btn_fullscreen.setToolTip("Развернуть окно на весь экран (F11)")
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        btn_layout.addWidget(self.btn_fullscreen, 2, 0, 1, 2)   # растянуть на 2 колонки
# ============
        control_layout.addLayout(btn_layout)
        
        # Кнопки OK и Cancel
        dialog_buttons = QHBoxLayout()
        dialog_buttons.setSpacing(5)
        
        self.btn_result = QPushButton("Результат")
        self.btn_result.setFixedHeight(28)
        self.btn_result.clicked.connect(self.show_results)
        self.btn_result.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        dialog_buttons.addWidget(self.btn_result)
        
        self.btn_ok = QPushButton("Записать жеребьевку")
        self.btn_ok.setFixedHeight(28)
        self.btn_ok.clicked.connect(self.on_save_clicked)
        self.btn_ok.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        dialog_buttons.addWidget(self.btn_ok)
        
        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.setFixedHeight(28)
        self.btn_cancel.clicked.connect(self.reject)
        dialog_buttons.addWidget(self.btn_cancel)
        
        control_layout.addLayout(dialog_buttons)
        
        # Инструкция - делаем более компактной
        info_text = QTextEdit()
        info_text.setMaximumHeight(120)  # Уменьшено с 150
        info_text.setReadOnly(True)
        info_text.setStyleSheet("font-size: 9px;")
        info_text.setPlainText("Правила:\n"
                            "• 1 номера групп - автоматически\n"
                            "• Желтая подсветка - текущая группа\n"
                            "• Клик по зеленой/желтой ячейке\n"
                            "• Зеленые - можно сеять\n"
                            "• Желтые - конфликт региона\n"
                            "• Красные - конфликт региона+тренера\n"
                            "• Двойной клик - редактирование")
        control_layout.addWidget(info_text)
        
        left_layout.addWidget(control_group)
        
        # ========== ЦЕНТРАЛЬНАЯ ПАНЕЛЬ ==========
        center_panel = QFrame()
        center_panel.setFrameStyle(QFrame.StyledPanel)
        center_layout = QVBoxLayout(center_panel)
        center_layout.setSpacing(3)
        
        lbl_groups = QLabel(f"Жеребьевка групп (групп: {self.num_groups}, макс: {self.max_rows_per_group})")
        lbl_groups.setStyleSheet("font-weight: bold; font-size: 12px;")
        center_layout.addWidget(lbl_groups)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.groups_widget = QWidget()
        self.groups_layout = QGridLayout(self.groups_widget)
        self.groups_layout.setAlignment(Qt.AlignTop)
        self.groups_layout.setVerticalSpacing(8)  # Уменьшено с 15
        self.groups_layout.setHorizontalSpacing(8)  # Уменьшено с 10
        self.groups_layout.setContentsMargins(5, 5, 5, 5)
        scroll_area.setWidget(self.groups_widget)
        center_layout.addWidget(scroll_area)
        
        content_layout.addWidget(left_panel)
        content_layout.addWidget(center_panel, stretch=1)
        
        main_layout.addLayout(content_layout)
 # ======================================================  
    def on_save_clicked(self):
        """Сохранение в БД и закрытие диалога только при успехе."""
        if self.save_to_database():
            self.accept()

    def get_group_players_count(self, group_idx):
        """Получить количество игроков в группе"""
        if group_idx < len(self.groups):
            return len([a for a in self.groups[group_idx] if a is not None])
        return 0
    
    def find_next_group_for_seed(self):
        """Найти следующую группу для посева (с наименьшим количеством игроков)"""
        groups_info = []
        for g in range(self.num_groups):
            count = self.get_group_players_count(g)
            groups_info.append((g, count))
        
        if not groups_info:
            return 0
            
        min_count = min(count for _, count in groups_info)
        min_groups = [g for g, count in groups_info if count == min_count]
        
        if self.current_round % 2 == 1:
            for g in min_groups:
                if g >= self.current_group_for_seed:
                    return g
            return min_groups[0]
        else:
            for g in reversed(min_groups):
                if g <= self.current_group_for_seed:
                    return g
            return min_groups[-1]
    
    def move_to_next_group(self):
        """Переход к следующей группе"""
        self.update_round_display()
        next_group = self.find_next_group_for_seed()
        self.current_group_for_seed = next_group
        self.highlight_current_group()
    
    def highlight_current_group(self):
        """Подсветка текущей группы для посева"""
        for header in self.group_headers:
            header.setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white; padding: 5px;")
        
        if self.current_group_for_seed is not None and self.current_group_for_seed < len(self.group_headers):
            self.group_headers[self.current_group_for_seed].setStyleSheet(
                "font-weight: bold; background-color: #FF9800; color: white; padding: 5px; border: 3px solid #FF5722;"
            )
            players_count = self.get_group_players_count(self.current_group_for_seed)
            self.current_group_label.setText(f"Группа: {self.current_group_for_seed + 1}\nИгроков: {players_count}")
    
    def load_athletes(self):
        """Загрузка и сортировка спортсменов"""
        self.sorted_athletes = sorted(self.athletes, key=lambda x: x[2], reverse=True)
        self.update_athletes_table()
        self.update_current_athlete()
        
    def update_athletes_table(self):
        """Обновление таблицы участников"""
        remaining_athletes = self.sorted_athletes[self.current_athlete_index:]
        
        self.athletes_table.setRowCount(len(remaining_athletes))
        for row, athlete in enumerate(remaining_athletes):
            id_player, name, rating, region, coach = athlete
            self.athletes_table.setItem(row, 0, QTableWidgetItem(str(id_player)))
            self.athletes_table.setItem(row, 1, QTableWidgetItem(name))
            self.athletes_table.setItem(row, 2, QTableWidgetItem(str(rating)))
            self.athletes_table.setItem(row, 3, QTableWidgetItem(region))
        
        self.athletes_table.resizeColumnsToContents()
        
    def init_groups(self):
        """Инициализация таблиц групп"""
        for i in reversed(range(self.groups_layout.count())):
            widget = self.groups_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        self.group_tables.clear()
        self.group_headers.clear()
        
        cols = min(4, self.num_groups)

        for g in range(self.num_groups):
            group_frame = QFrame()
            group_frame.setFrameStyle(QFrame.Box)
            group_frame.setMinimumWidth(260)  # Уменьшено с 300
            group_frame.setMaximumWidth(400)  # Уменьшено с 400
            group_layout = QVBoxLayout(group_frame)
            group_layout.setSpacing(3)
            
            header = QLabel(f"Группа {g+1}")
            header.setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white; padding: 3px; font-size: 11px;")
            header.setAlignment(Qt.AlignCenter)
            group_layout.addWidget(header)
            
            table = QTableWidget()
            table.setColumnCount(2)
            table.setHorizontalHeaderLabels(["№", "Участник"])
           
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
            table.setColumnWidth(0, 40)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            
            table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            
            table.setRowCount(self.max_rows_per_group)
            
            table.verticalHeader().setVisible(False)
            table.setAlternatingRowColors(True)
            table.setSelectionBehavior(QTableWidget.SelectItems)
            table.cellClicked.connect(self.on_cell_clicked)
            # ==== old
            # table.setEditTriggers(QTableWidget.DoubleClicked)
            table.setEditTriggers(QTableWidget.NoEditTriggers)
            # ==================================================
            table.itemDoubleClicked.connect(self.on_item_double_clicked)
            
            table.setMouseTracking(True)
            table.cellEntered.connect(self.on_cell_entered)
            
            for row in range(self.max_rows_per_group):
                num_item = QTableWidgetItem(str(row + 1))
                num_item.setTextAlignment(Qt.AlignCenter)
                num_item.setFlags(num_item.flags() & ~Qt.ItemIsEditable)
                table.setItem(row, 0, num_item)
                table.setRowHeight(row, 22)
            
            group_layout.addWidget(table)
            
            table_height = table.horizontalHeader().height() + 2
            table_height += self.max_rows_per_group * 22
            table.setFixedHeight(table_height + 5)
            
            row = g // cols
            col = g % cols
            self.groups_layout.addWidget(group_frame, row, col)
            
            self.group_tables.append(table)
            self.group_headers.append(header)
        
        self.groups_layout.setSpacing(15)
        self.groups_layout.setContentsMargins(10, 10, 10, 10)
        
        if not self.groups:
            self.groups = [[] for _ in range(self.num_groups)]
        
        self.update_groups_display()
        self.highlight_current_group()
    
    def on_cell_entered(self, row, col):
        """Обработка наведения мыши на ячейку"""
        if col != 1:
            return
        
        table = self.sender()
        if not table:
            return
        
        for g_idx, t in enumerate(self.group_tables):
            if t == table:
                if g_idx < len(self.groups) and row < len(self.groups[g_idx]) and self.groups[g_idx][row]:
                    athlete = self.groups[g_idx][row]
                    if athlete:
                        id_player, name, rating, region, coach = athlete
                        tooltip_text = f"ID: {id_player}\nФИО: {name}\nРейтинг: {rating}\nРегион: {region}\nТренер: {coach}"
                        QToolTip.showText(QCursor.pos(), tooltip_text)
                break
    
    def update_groups_display(self):
        """Обновление отображения всех групп"""
        for g_idx, table in enumerate(self.group_tables):
            for row in range(self.max_rows_per_group):
                if g_idx < len(self.groups) and row < len(self.groups[g_idx]) and self.groups[g_idx][row]:
                    athlete = self.groups[g_idx][row]
                    if athlete:
                        id_player, name, rating, region, coach = athlete
                        display_text = f"{name} ({region}) R:{rating}"
                        item = QTableWidgetItem(display_text)
                        item.setData(Qt.UserRole, id_player)
                        item.setFlags(item.flags() | Qt.ItemIsEditable)
                        item.setToolTip(f"ID: {id_player}\nФИО: {name}\nРейтинг: {rating}\nРегион: {region}\nТренер: {coach}")
                        table.setItem(row, 1, item)
                    else:
                        empty_item = QTableWidgetItem("")
                        empty_item.setFlags(empty_item.flags() | Qt.ItemIsEditable)
                        table.setItem(row, 1, empty_item)
                else:
                    empty_item = QTableWidgetItem("")
                    empty_item.setFlags(empty_item.flags() | Qt.ItemIsEditable)
                    table.setItem(row, 1, empty_item)
        
        self.update_stats()
        self.update_athletes_table()
        
    def update_stats(self):
        """Обновление статистики"""
        total = len(self.athletes)
        placed = self.current_athlete_index
        remaining = total - placed
        self.total_label.setText(str(total))
        self.placed_label.setText(str(placed))
        self.remaining_label.setText(str(remaining))
        self.max_rows_label.setText(str(self.max_rows_per_group))
        self.round_number_label.setText(str(self.current_round))
        self.update_current_athlete()
        
    def update_current_athlete(self):
        """Обновление отображения текущего спортсмена"""
        if self.current_athlete_index < len(self.sorted_athletes):
            athlete = self.sorted_athletes[self.current_athlete_index]
            id_player, name, rating, region, coach = athlete
            self.current_athlete_label.setText(f"Спортсмен: {name}\nРейтинг: {rating}\nРегион: {region}\nТренер: {coach}")
            self.highlight_available_cells(athlete)
        else:
            self.current_athlete_label.setText("Жеребьевка завершена!\nВсе спортсмены\nраспределены")
            self.current_athlete_label.setStyleSheet("background-color: #90EE90; padding: 8px; font-size: 12px;")
            self.highlight_available_cells(None)   # <-- NEW: сброс счётчиков в заголовках
# ========== old ===========    
    def check_conflicts(self, athlete, group_idx):
        """Проверка конфликтов"""
        if group_idx >= len(self.groups):
            return False, False
            
        _, _, _, region, coach = athlete
        
        group_regions = [a[3] for a in self.groups[group_idx] if a]
        group_coaches = [a[4] for a in self.groups[group_idx] if a]
        
        region_conflict = region in group_regions
        coach_conflict = coach in group_coaches and region_conflict
        
        return region_conflict, coach_conflict

    def highlight_available_cells(self, athlete):
        """Подсветка доступных ячеек + счётчик совпадений региона в заголовках групп."""
        # 1. Сброс подсветки и текста заголовков
        for g_idx, table in enumerate(self.group_tables):
            for row in range(table.rowCount()):
                num_item  = table.item(row, 0)
                name_item = table.item(row, 1)
                if num_item:
                    num_item.setBackground(QBrush(QColor(255, 255, 255)))
                if name_item:
                    name_item.setBackground(QBrush(QColor(255, 255, 255)))
            if g_idx < len(self.group_headers):
                self.group_headers[g_idx].setText(f"Группа {g_idx + 1}")
                self.group_headers[g_idx].setToolTip("")

        if not athlete:
            return

        target_region = athlete[3]

        # 2. Счётчик в заголовке + подсветка доступных ячеек
        for g_idx, table in enumerate(self.group_tables):
            region_count = 0
            if g_idx < len(self.groups):
                region_count = sum(1 for a in self.groups[g_idx]
                                if a and a[3] == target_region)

            if g_idx < len(self.group_headers) and region_count > 0:
                header = self.group_headers[g_idx]
                header.setText(f"Группа {g_idx + 1} ({region_count})")
                header.setToolTip(
                    f"В группе {g_idx + 1} уже {region_count} "
                    f"спортсмен(ов) из региона «{target_region}»"
                )

            for row in range(table.rowCount()):
                item = table.item(row, 1)
                if not item or not item.text():
                    region_conflict, coach_conflict = self.check_conflicts(athlete, g_idx)
                    num_item = table.item(row, 0)
                    if num_item:
                        if coach_conflict:
                            num_item.setBackground(QBrush(QColor(255, 100, 100)))
                        elif region_conflict:
                            num_item.setBackground(QBrush(QColor(255, 255, 150)))
                        else:
                            num_item.setBackground(QBrush(QColor(144, 238, 144)))

        # 3. Подсветка занятых ячеек с тем же регионом (без запросов к БД)
        for g_idx, table in enumerate(self.group_tables):
            if g_idx >= len(self.groups):
                continue
            for row in range(table.rowCount()):
                if row >= len(self.groups[g_idx]):
                    continue
                a = self.groups[g_idx][row]
                if a and a[3] == target_region:
                    item = table.item(row, 1)
                    if item:
                        item.setBackground(QBrush(QColor(255, 255, 150)))
    # ============
    def can_place_athlete(self, athlete, group_idx, row):
        """Проверка возможности размещения"""
        if group_idx >= len(self.groups):
            return False
            
        if row < len(self.groups[group_idx]) and self.groups[group_idx][row] is not None:
            return False
            
        return True
    
    def closeEvent(self, event):
        """Обработка закрытия окна через крестик"""
        if self.current_athlete_index < len(self.sorted_athletes):
            reply = QMessageBox.question(self, 'Подтверждение закрытия',
                f'Не все спортсмены распределены!\n'
                f'Осталось: {len(self.sorted_athletes) - self.current_athlete_index} спортсменов.\n\n'
                f'Вы уверены, что хотите закрыть окно жеребьевки?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def on_cell_clicked(self, row, col):
        if col != 1:
            return

        table = self.sender()
        if not table:
            return

        for g_idx, t in enumerate(self.group_tables):
            if t is not table:
                continue

            # 1) Ячейка занята → МОЛЧА выходим. Обработает on_item_double_clicked.
            if (g_idx < len(self.groups)
                    and row < len(self.groups[g_idx])
                    and self.groups[g_idx][row] is not None):
                return

            # 2) Некуда сажать
            if self.current_athlete_index >= len(self.sorted_athletes):
                QMessageBox.information(self, "Информация", "Все спортсмены уже размещены!")
                return

            current_athlete = self.sorted_athletes[self.current_athlete_index]

            region_conflict, coach_conflict = self.check_conflicts(current_athlete, g_idx)

            if coach_conflict:
                QMessageBox.warning(self, "Запрещено!",
                    f"Нельзя разместить {current_athlete[1]} в группу {g_idx + 1}!\n"
                    f"В группе уже есть спортсмен с таким же регионом ({current_athlete[3]}) "
                    f"и тренером ({current_athlete[4]}).")
                return

            if region_conflict:
                reply = QMessageBox.question(self, 'Конфликт регионов',
                    f'В группе {g_idx + 1} уже есть спортсмен из региона {current_athlete[3]}.\n'
                    f'Разместить {current_athlete[1]} в эту группу?',
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No:
                    return

            while len(self.groups[g_idx]) <= row:
                self.groups[g_idx].append(None)
            self.groups[g_idx][row] = current_athlete

            # <-- NEW: запомним «только что поставили», чтобы двойной клик
            #          по этой же ячейке сразу не снял игрока
            self._last_placed = (g_idx, row, time.time())

            display_text = f"{current_athlete[1]} ({current_athlete[3]}) R:{current_athlete[2]}"
            item = QTableWidgetItem(display_text)
            item.setData(Qt.UserRole, current_athlete[0])
            item.setToolTip(f"ID: {current_athlete[0]}\nФИО: {current_athlete[1]}\n"
                            f"Рейтинг: {current_athlete[2]}\nРегион: {current_athlete[3]}\n"
                            f"Тренер: {current_athlete[4]}")
            table.setItem(row, 1, item)

            self.current_athlete_index += 1
            self.update_round_display()

            if g_idx == self.current_group_for_seed:
                self.move_to_next_group()
            else:
                self.highlight_current_group()

            if self.current_athlete_index < len(self.sorted_athletes):
                self.highlight_available_cells(self.sorted_athletes[self.current_athlete_index])

            self.update_stats()
            self.update_athletes_table()

            if self.current_athlete_index >= len(self.sorted_athletes):
                QMessageBox.information(self, "Поздравляем!", "Жеребьевка успешно завершена!")
            break

    def unplace_athlete(self, g_idx, row):
        """Убирает спортсмена из группы и возвращает его в общий список для жеребьёвки."""
        if g_idx >= len(self.groups) or row >= len(self.groups[g_idx]):
            return
        athlete = self.groups[g_idx][row]
        if not athlete:
            return

        # Очищаем ячейку в модели данных
        self.groups[g_idx][row] = None

        # Пересобираем отсортированный список спортсменов на основе фактического размещения
        placed_ids = set()
        for group in self.groups:
            for a in group:
                if a:
                    placed_ids.add(a[0])

        placed_athletes   = [a for a in self.athletes if a[0] in placed_ids]
        unplaced_athletes = [a for a in self.athletes if a[0] not in placed_ids]
        placed_athletes.sort(key=lambda x: x[2], reverse=True)
        unplaced_athletes.sort(key=lambda x: x[2], reverse=True)

        self.sorted_athletes = placed_athletes + unplaced_athletes
        self.current_athlete_index = len(placed_athletes)

        # Полное обновление интерфейса
        self.update_round_display()
        self.update_groups_display()
        self.highlight_current_group()

    def on_item_double_clicked(self, item):
        if item.column() != 1:
            return

        table = item.tableWidget()
        row = item.row()

        for g_idx, t in enumerate(self.group_tables):
            if t is not table:
                continue

            # Защита: если это двойной клик по ПУСТОЙ ячейке, и первый клик
            # только что поставил туда спортсмена — не снимаем его.
            lp = self._last_placed
            if lp and lp[0] == g_idx and lp[1] == row and (time.time() - lp[2]) < 0.5:
                return

            athlete = None
            if g_idx < len(self.groups) and row < len(self.groups[g_idx]):
                athlete = self.groups[g_idx][row]

            if athlete:
                reply = QMessageBox.question(
                    self, 'Убрать из группы',
                    f'Убрать спортсмена «{athlete[1]}» из группы {g_idx + 1}?\n\n'
                    f'Он вернётся в список спортсменов для повторной жеребьёвки.',
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if reply == QMessageBox.Yes:
                    self.unplace_athlete(g_idx, row)
            else:
                self.edit_cell(g_idx, row)
            break
 # ===============   
    def edit_cell(self, group_idx, row):
        """Редактирование конкретной ячейки"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Редактирование ячейки")
        dialog.setModal(True)
        dialog.setMinimumWidth(500)
        layout = QVBoxLayout(dialog)
        
        all_unplaced = self.sorted_athletes[self.current_athlete_index:]
        
        list_widget = QListWidget()
        
        current_athlete = None
        if group_idx < len(self.groups) and row < len(self.groups[group_idx]):
            current_athlete = self.groups[group_idx][row]
            if current_athlete:
                list_widget.addItem(f"--- Текущий: {current_athlete[1]} (Рейтинг: {current_athlete[2]}, Тренер: {current_athlete[4]}) ---")
        
        for athlete in all_unplaced:
            list_widget.addItem(f"{athlete[1]} (Рейтинг: {athlete[2]}, Регион: {athlete[3]}, Тренер: {athlete[4]})")
        
        list_widget.addItem("--- Очистить ячейку ---")
        
        layout.addWidget(QLabel("Выберите спортсмена для размещения:"))
        layout.addWidget(list_widget)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        
        def on_accept():
            selected = list_widget.currentRow()
            if selected >= 0:
                offset = 1 if current_athlete else 0
                
                if selected < len(all_unplaced) + offset:
                    athlete_idx = selected - offset
                    if athlete_idx >= 0 and athlete_idx < len(all_unplaced):
                        athlete = all_unplaced[athlete_idx]
                        
                        region_conflict, coach_conflict = self.check_conflicts(athlete, group_idx)
                        
                        if coach_conflict:
                            QMessageBox.warning(dialog, "Запрещено!",
                                f"Нельзя разместить {athlete[1]} в группу {group_idx + 1}!\n"
                                f"В группе уже есть спортсмен с таким же регионом и тренером.")
                            return
                        
                        if region_conflict:
                            reply = QMessageBox.question(dialog, 'Конфликт регионов',
                                f'В группе {group_idx + 1} уже есть спортсмен из региона {athlete[3]}.\n'
                                f'Все равно разместить?',
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                            
                            if reply == QMessageBox.No:
                                return
                        
                        old_athlete = None
                        if group_idx < len(self.groups) and row < len(self.groups[group_idx]):
                            old_athlete = self.groups[group_idx][row]
                        
                        while len(self.groups[group_idx]) <= row:
                            self.groups[group_idx].append(None)
                        self.groups[group_idx][row] = athlete
                        
                        table = self.group_tables[group_idx]
                        display_text = f"{athlete[1]} ({athlete[3]}) R:{athlete[2]}"
                        item = QTableWidgetItem(display_text)
                        item.setData(Qt.UserRole, athlete[0])
                        item.setFlags(item.flags() | Qt.ItemIsEditable)
                        item.setToolTip(f"ID: {athlete[0]}\nФИО: {athlete[1]}\nРейтинг: {athlete[2]}\nРегион: {athlete[3]}\nТренер: {athlete[4]}")
                        table.setItem(row, 1, item)
                        
                        if athlete in self.sorted_athletes:
                            idx = self.sorted_athletes.index(athlete)
                            if idx >= self.current_athlete_index:
                                self.sorted_athletes.pop(idx)
                                if idx < self.current_athlete_index:
                                    self.current_athlete_index -= 1
                        
                        if old_athlete:
                            self.sorted_athletes.insert(self.current_athlete_index, old_athlete)
                        
                        self.update_athletes_table()
                        self.update_stats()
                        self.update_current_athlete()
                        dialog.accept()
                elif selected == len(all_unplaced) + offset:
                    if group_idx < len(self.groups) and row < len(self.groups[group_idx]):
                        athlete = self.groups[group_idx][row]
                        self.groups[group_idx][row] = None
                        
                        table = self.group_tables[group_idx]
                        table.setItem(row, 1, QTableWidgetItem(""))
                        
                        if athlete:
                            self.sorted_athletes.insert(self.current_athlete_index, athlete)
                            self.update_athletes_table()
                            self.update_stats()
                            self.update_current_athlete()
                            dialog.accept()
            else:
                QMessageBox.warning(dialog, "Ошибка", "Выберите спортсмена!")
        
        buttons.accepted.connect(on_accept)
        buttons.rejected.connect(dialog.reject)
        dialog.exec_()

    def open_editor(self):
        """Открыть редактор для обмена игроками между группами"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Редактор групп")
        dialog.setModal(True)
        dialog.setMinimumSize(800, 500)
        dialog.setMaximumSize(1000, 600)
        
        layout = QVBoxLayout(dialog)
        
        group_combos = []
        group_labels = []
        
        # Создаем копию текущих данных групп для редактирования
        group_data = []
        for g_idx in range(self.num_groups):
            group_copy = []
            for athlete in self.groups[g_idx]:
                group_copy.append(athlete)
            group_data.append(group_copy)
        
        scroll_widget = QWidget()
        scroll_layout = QGridLayout(scroll_widget)
        
        cols = min(4, self.num_groups)
        for g_idx in range(self.num_groups):
            group_frame = QFrame()
            group_frame.setFrameStyle(QFrame.Box)
            group_frame.setMaximumWidth(250)
            group_layout = QVBoxLayout(group_frame)
            group_layout.setSpacing(5)
            
            label = QLabel(f"Группа {g_idx + 1}")
            label.setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white; padding: 3px;")
            label.setAlignment(Qt.AlignCenter)
            group_layout.addWidget(label)
            
            combo = QComboBox()
            combo.setMaximumWidth(230)
            combo.setProperty("group_idx", g_idx)
            combo.addItem("--- Выберите спортсмена для перемещения ---")
            
            for row, athlete in enumerate(group_data[g_idx]):
                if athlete:
                    short_name = athlete[1][:15] + "..." if len(athlete[1]) > 15 else athlete[1]
                    # Сохраняем полную информацию о спортсмене
                    combo.addItem(f"{row+1}. {short_name} ({athlete[3][:10]}) R:{athlete[2]}", (g_idx, row, athlete))
            
            group_layout.addWidget(combo)
            group_combos.append(combo)
            group_labels.append(label)
            
            scroll_layout.addWidget(group_frame, g_idx // cols, g_idx % cols)
        
        scroll_area = QScrollArea()
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        btn_layout = QHBoxLayout()
        
        btn_swap = QPushButton("Обменять выбранных")
        btn_swap.setStyleSheet("background-color: #2196F3; color: white; padding: 8px;")
        btn_layout.addWidget(btn_swap)
        
        btn_move = QPushButton("Переместить")
        btn_move.setStyleSheet("background-color: #FF9800; color: white; padding: 8px;")
        btn_layout.addWidget(btn_move)
        
        btn_save = QPushButton("Сохранить изменения")
        btn_save.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px;")
        btn_layout.addWidget(btn_save)
        
        btn_cancel = QPushButton("Отмена")
        btn_cancel.setStyleSheet("background-color: #f44336; color: white; padding: 8px;")
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)
        
        selected_athletes = []  # Список выбранных спортсменов (группа, индекс, спортсмен, комбобокс)
        
        def get_current_athlete_position(athlete, group_idx):
            """Получить актуальную позицию спортсмена в группе"""
            for idx, a in enumerate(group_data[group_idx]):
                if a and a[0] == athlete[0]:  # Сравниваем по ID
                    return idx
            return -1
        
        def refresh_combos():
            """Обновить все комбобоксы после изменений"""
            for g_idx in range(self.num_groups):
                current_text = group_combos[g_idx].currentText()
                current_data = group_combos[g_idx].currentData() if group_combos[g_idx].currentIndex() > 0 else None
                
                group_combos[g_idx].clear()
                group_combos[g_idx].addItem("--- Выберите спортсмена для перемещения ---")
                
                for row, athlete in enumerate(group_data[g_idx]):
                    if athlete:
                        short_name = athlete[1][:15] + "..." if len(athlete[1]) > 15 else athlete[1]
                        group_combos[g_idx].addItem(f"{row+1}. {short_name} ({athlete[3][:10]}) R:{athlete[2]}", (g_idx, row, athlete))
                
                group_combos[g_idx].setEnabled(True)
                group_labels[g_idx].setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white; padding: 3px;")
                
                # Восстанавливаем выбранный элемент если возможно
                if current_data:
                    for i in range(group_combos[g_idx].count()):
                        data = group_combos[g_idx].itemData(i)
                        if data and data[2][0] == current_data[2][0]:  # Сравниваем по ID
                            group_combos[g_idx].setCurrentIndex(i)
                            break
            
            # Очищаем список выбранных спортсменов
            selected_athletes.clear()
        
        def on_combo_change(idx, group_idx):
            if idx > 0:
                athlete_data = group_combos[group_idx].itemData(idx)
                if athlete_data:
                    # Проверяем, не выбран ли уже этот спортсмен
                    for existing in selected_athletes:
                        if existing[2][0] == athlete_data[2][0]:  # Сравниваем по ID
                            QMessageBox.warning(dialog, "Ошибка", "Этот спортсмен уже выбран!")
                            group_combos[group_idx].setCurrentIndex(0)
                            return
                    
                    selected_athletes.append((group_idx, athlete_data[1], athlete_data[2], group_combos[group_idx]))
                    group_combos[group_idx].setEnabled(False)
                    group_labels[group_idx].setStyleSheet("font-weight: bold; background-color: #FF9800; color: white; padding: 3px;")
        
        for g_idx, combo in enumerate(group_combos):
            combo.currentIndexChanged.connect(lambda idx, g=g_idx: on_combo_change(idx, g))
        
        def swap_athletes():
            if len(selected_athletes) == 2:
                g1, row1, athlete1, combo1 = selected_athletes[0]
                g2, row2, athlete2, combo2 = selected_athletes[1]
                
                # Получаем актуальные позиции спортсменов
                actual_row1 = get_current_athlete_position(athlete1, g1)
                actual_row2 = get_current_athlete_position(athlete2, g2)
                
                if actual_row1 == -1 or actual_row2 == -1:
                    QMessageBox.warning(dialog, "Ошибка", "Спортсмен не найден в группе!")
                    refresh_combos()
                    return
                
                # Проверяем конфликты при обмене
                conflict1 = False
                conflict2 = False
                
                # Проверяем для группы 1 с athlete2
                group1_regions = [a[3] for a in group_data[g1] if a and a[0] != athlete1[0]]
                if athlete2[3] in group1_regions:
                    group1_coaches = [a[4] for a in group_data[g1] if a and a[0] != athlete1[0]]
                    if athlete2[4] in group1_coaches:
                        conflict1 = True
                
                # Проверяем для группы 2 с athlete1
                group2_regions = [a[3] for a in group_data[g2] if a and a[0] != athlete2[0]]
                if athlete1[3] in group2_regions:
                    group2_coaches = [a[4] for a in group_data[g2] if a and a[0] != athlete2[0]]
                    if athlete1[4] in group2_coaches:
                        conflict2 = True
                
                if conflict1 or conflict2:
                    QMessageBox.warning(dialog, "Запрещено!",
                        "Обмен невозможен! Будет нарушено правило совпадения региона и тренера.")
                    return
                
                # Выполняем обмен
                group_data[g1][actual_row1], group_data[g2][actual_row2] = athlete2, athlete1
                
                refresh_combos()
                QMessageBox.information(dialog, "Успех", "Спортсмены успешно обменяны!")
            else:
                QMessageBox.warning(dialog, "Ошибка", "Выберите ровно двух спортсменов для обмена!")
        
        def move_athlete():
            if len(selected_athletes) == 1:
                g1, row1, athlete1, combo1 = selected_athletes[0]
                
                # Получаем актуальную позицию спортсмена
                actual_row1 = get_current_athlete_position(athlete1, g1)
                
                if actual_row1 == -1:
                    QMessageBox.warning(dialog, "Ошибка", "Спортсмен не найден в группе!")
                    refresh_combos()
                    return
                
                # Создаем диалог выбора цели
                target_dialog = QDialog(dialog)
                target_dialog.setWindowTitle("Выберите цель")
                target_layout = QVBoxLayout(target_dialog)
                target_dialog.setFixedSize(450, 300)
                
                target_layout.addWidget(QLabel("Выберите группу:"))
                target_combo = QComboBox()
                available_groups = [f"Группа {i+1}" for i in range(self.num_groups) if i != g1]
                target_combo.addItems(available_groups)
                target_layout.addWidget(target_combo)
                
                target_layout.addWidget(QLabel("Выберите строку (номер посева):"))
                target_row_combo = QComboBox()
                target_layout.addWidget(target_row_combo)
                
                def update_row_status():
                    target_row_combo.clear()
                    target_group_name = target_combo.currentText()
                    target_group = int(target_group_name.split()[1]) - 1
                    
                    # Определяем максимальное количество строк
                    max_rows = max(self.max_rows_per_group, len(group_data[target_group]) + 5)
                    
                    for i in range(max_rows):
                        # Проверяем, занято ли место
                        is_occupied = False
                        if i < len(group_data[target_group]) and group_data[target_group][i] is not None:
                            is_occupied = True
                        status = " (занято)" if is_occupied else " (свободно)"
                        target_row_combo.addItem(f"{i+1}{status}", i)
                
                update_row_status()
                target_combo.currentIndexChanged.connect(update_row_status)
                
                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                target_layout.addWidget(buttons)
                
                def do_move():
                    target_group_name = target_combo.currentText()
                    target_group = int(target_group_name.split()[1]) - 1
                    target_row = target_row_combo.currentData()
                    
                    # Проверяем, что целевая строка существует и не занята
                    if target_group >= len(group_data):
                        QMessageBox.warning(self, "Ошибка", "Целевая группа не существует!")
                        return
                    
                    # Расширяем список группы если нужно
                    while len(group_data[target_group]) <= target_row:
                        group_data[target_group].append(None)
                    
                    if group_data[target_group][target_row] is not None:
                        QMessageBox.warning(self, "Ошибка", "Это место уже занято!")
                        return
                    
                    # Проверяем конфликты при перемещении
                    group_target_regions = [a[3] for a in group_data[target_group] if a]
                    group_target_coaches = [a[4] for a in group_data[target_group] if a]
                    
                    region_conflict = athlete1[3] in group_target_regions
                    coach_conflict = athlete1[4] in group_target_coaches and region_conflict
                    
                    if coach_conflict:
                        QMessageBox.warning(self, "Запрещено!",
                            f"Нельзя переместить {athlete1[1]} в группу {target_group + 1}!\n"
                            f"В группе уже есть спортсмен с таким же регионом и тренером.")
                        return
                    
                    if region_conflict:
                        reply = QMessageBox.question(target_dialog, 'Конфликт регионов',
                            f'В группе {target_group + 1} уже есть спортсмен из региона {athlete1[3]}.\n'
                            f'Все равно переместить?',
                            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                        
                        if reply == QMessageBox.No:
                            return
                    
                    # Выполняем перемещение
                    group_data[g1][actual_row1] = None
                    group_data[target_group][target_row] = athlete1
                    
                    target_dialog.accept()
                    refresh_combos()
                    QMessageBox.information(dialog, "Успех", "Спортсмен успешно перемещен!")
                
                buttons.accepted.connect(do_move)
                buttons.rejected.connect(target_dialog.reject)
                target_dialog.exec_()
            else:
                QMessageBox.warning(self, "Ошибка", "Выберите одного спортсмена для перемещения!")
        
        def save_changes():
            """Сохранить изменения и обновить основное отображение"""
            # Обновляем основные данные групп, удаляя None значения
            self.groups = []
            for g_idx in range(self.num_groups):
                group = []
                for athlete in group_data[g_idx]:
                    if athlete:
                        group.append(athlete)
                self.groups.append(group)
            
            # Обновляем индекс текущего спортсмена
            placed_count = sum(1 for group in self.groups for athlete in group if athlete)
            self.current_athlete_index = placed_count
            
            # Обновляем отображение
            self.update_groups_display()
            self.update_athletes_table()
            self.update_stats()
            self.update_current_athlete()
            
            # Пересчитываем текущую группу для посева
            self.current_group_for_seed = self.find_next_group_for_seed()
            self.highlight_current_group()
            
            dialog.accept()
            QMessageBox.information(self, "Успех", "Изменения сохранены!")
        
        btn_swap.clicked.connect(swap_athletes)
        btn_move.clicked.connect(move_athlete)
        btn_save.clicked.connect(save_changes)
        btn_cancel.clicked.connect(dialog.reject)
        
        dialog.exec_() 

    def reset_draw(self):
        """Полный сброс"""
        self.load_athletes()
        self.current_athlete_index = 0
        self.groups = [[] for _ in range(self.num_groups)]
        self.current_group_for_seed = self.num_groups - 1
        self.init_groups()
        self.update_round_display()
        self.highlight_current_group()
        self.current_athlete_label.setStyleSheet("background-color: #ffe0b3; padding: 8px; font-size: 12px;")
    
    def auto_fill_first(self):
        """Автоматическое заполнение первых номеров"""
        self.reset_draw()
        
        for i in range(min(self.num_groups, len(self.sorted_athletes))):
            self.groups[i] = [self.sorted_athletes[i]]
            table = self.group_tables[i]
            athlete = self.sorted_athletes[i]
            display_text = f"{athlete[1]} ({athlete[3]}) R:{athlete[2]}"
            item = QTableWidgetItem(display_text)
            item.setData(Qt.UserRole, athlete[0])
            item.setToolTip(f"ID: {athlete[0]}\nФИО: {athlete[1]}\nРейтинг: {athlete[2]}\nРегион: {athlete[3]}\nТренер: {athlete[4]}")
            table.setItem(0, 1, item)
            self.current_athlete_index += 1
        
        self.update_round_display()
        self.current_group_for_seed = self.find_next_group_for_seed()
        self.update_athletes_table()
        self.update_stats()
        self.highlight_current_group()
    
    def clear_all_groups(self):
        """Очистка всех групп"""
        all_athletes = []
        for group in self.groups:
            for athlete in group:
                if athlete:
                    all_athletes.append(athlete)
        
        self.groups = [[] for _ in range(self.num_groups)]
        self.sorted_athletes = sorted(all_athletes + self.sorted_athletes[self.current_athlete_index:], 
                                     key=lambda x: x[2], reverse=True)
        self.current_athlete_index = 0
        self.current_group_for_seed = self.num_groups - 1
        
        for table in self.group_tables:
            for row in range(self.max_rows_per_group):
                table.setItem(row, 1, QTableWidgetItem(""))
        
        self.update_athletes_table()
        self.update_stats()
        self.update_round_display()
        self.highlight_current_group()
        self.update_current_athlete()
    
    def _show_results(self):
        """Показать результаты"""
        results = []
        for group_idx, group in enumerate(self.groups):
            gr = group_idx + 1
            for seed_num, athlete in enumerate(group, 1):
                if athlete:
                    results.append([
                        seed_num,
                        athlete[0],
                        athlete[1],
                        athlete[3],
                        gr
                    ])
        
        results.sort(key=lambda x: x[0])
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Результаты жеребьевки")
        dialog.setModal(True)
        dialog.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        result_table = QTableWidget()
        result_table.setColumnCount(4)
        result_table.setHorizontalHeaderLabels(["№ посева", "ID игрока", "ФИО", "Регион"])
        result_table.setRowCount(len(results))
        
        for row, result in enumerate(results):
            for col, value in enumerate(result):
                result_table.setItem(row, col, QTableWidgetItem(str(value)))
        
        result_table.horizontalHeader().setStretchLastSection(True)
        result_table.resizeColumnsToContents()
        
        layout.addWidget(QLabel("Результаты жеребьевки:"))
        layout.addWidget(result_table)
        
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close)
        
        dialog.exec_()
    
    def show_results(self):
        """показать результаты жереьевки в pdf"""
        pass

    def get_results(self):
        """Получить результаты жеребьевки"""
        results = []
        for group_idx, group in enumerate(self.groups):
            gr = group_idx + 1
            for seed_num, athlete in enumerate(group, 1):
                if athlete:
                    results.append({
                        'seed_num': seed_num,
                        'id_player': athlete[0],
                        'name': athlete[1],
                        'region': athlete[3],
                        'group': gr
                    })
        return results
# ==== вариант восстановления сохранения ===
    def save_to_database(self):
        """Сохраняет результаты жеребьёвки в Choice (по текущему title_id/sex/stage).
        Возвращает True при успехе."""
        try:
            # System для квалификации (по текущему турниру/полу/этапу)
            stage = "Квалификация"
            system = System.get_or_none(
                (System.title_id == self.title_id) &
                (System.sex == self.sex) &
                (System.stage == stage)
            )
            if not system:
                system = System.create(
                    title_id=self.title_id,
                    sex=self.sex,
                    stage=stage,
                    total_group=self.num_groups,
                    max_player=self.max_rows_per_group,
                    type_table="Круговая",
                    score_flag=5,
                )
            else:
                # обновим параметры на случай смены количества групп
                system.total_group = self.num_groups
                system.max_player = self.max_rows_per_group
                if not getattr(system, "sex", None):
                    system.sex = self.sex
                system.save()

            # Сбрасываем только записи этого турнира/пола
            Choice.update(
                group=None, posev_group=None
            ).where(
                (Choice.title_id == self.title_id) &
                (Choice.sex == self.sex)
            ).execute()

            # Записываем позиции
            for group_idx, group in enumerate(self.groups):
                gr_num = group_idx + 1
                for posev_group, athlete in enumerate(group, 1):
                    if not athlete:
                        continue

                    choice = Choice.get_or_none(
                        (Choice.title_id == self.title_id) &
                        (Choice.sex == self.sex) &
                        (Choice.player_choice_id == athlete[0])
                    )
                    if not choice:
                        # На всякий случай: если игрока нет в Choice — создаём
                        choice = Choice.create(
                            title_id=self.title_id,
                            sex=self.sex,
                            player_choice_id=athlete[0],
                            system_id=system.id,
                        )
                    choice.group = f"{gr_num} группа"
                    choice.posev_group = posev_group
                    choice.system_id = system.id
                    choice.save()

            # Флаг выбора
            system.choice_flag = True
            system.save()

            QMessageBox.information(
                self, "Успех",
                f"Результаты сохранены.\n"
                f"Распределено спортсменов: "
                f"{sum(1 for g in self.groups for a in g if a)}"
            )
            return True

        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Ошибка сохранения:\n{str(e)}")
            return False
# ======== new
    def toggle_fullscreen(self):
        """Переключение между полноэкранным и обычным режимом."""
        if self.is_fullscreen:
            # Выход из полного экрана
            if self._saved_geometry is not None:
                self.setGeometry(self._saved_geometry)
            self.showNormal()
            self.is_fullscreen = False
            self.btn_fullscreen.setText("⛶ Полный экран (F11)")
        else:
            # Запоминаем геометрию и разворачиваем
            self._saved_geometry = self.geometry()
            self.showFullScreen()
            self.is_fullscreen = True
            self.btn_fullscreen.setText("⤡ Выйти из полного экрана (F11)")

        # После смены режима пересчитываем размеры таблиц групп,
        # чтобы содержимое заняло всё пространство
        self._refresh_group_view()

    def _refresh_group_view(self):
        """Перестраивает таблицы групп под текущий размер окна."""
        try:
            self.update_groups_display()
            self.update_round_display()
        except Exception as e:
            print(f"[toggle_fullscreen] refresh failed: {e}")
# ===========
# def load_existing_draw_from_db(id_title, current_sex):
#     """Загрузка существующей жеребьевки из базы данных через Peewee"""
#     choices = Choice.select().where((Choice.title_id == id_title) & (Choice.sex == current_sex))
#     try:
#         results = choices.select().order_by(Choice.group, Choice.posev_group)
#         return list(results) if results.exists() else None
#     except Exception as e:
#         print(f"Ошибка при загрузке из базы данных: {e}")
#         return None

def load_existing_draw_from_db(id_title, current_sex, stage="Квалификация"):
    system = System.get_or_none(
        (System.title_id == id_title) &
        (System.sex == current_sex) &
        (System.stage == stage)
    )
    if not system:
        return None
    q = (Choice.select()
         .where((Choice.title_id == id_title) &
                (Choice.sex == current_sex) &
                (Choice.system_id == system.id) &
                (Choice.group.is_null(False)) &
                (Choice.posev_group.is_null(False)))
         .order_by(Choice.group, Choice.posev_group))
    return list(q) if q.exists() else None

# def clear_db_before_choice(self, stage):
#     """очищает базу данных -Game_list- и -Result- перед повторной жеребьевкой групп"""

#     systems = System.select().where((System.stage == stage) & (System.title_id == self)).get()
#     id_system = systems.id

#     gamelist = Game_list.select().where((Game_list.title_id == self) & (Game_list.system_id == id_system))
#     for i in gamelist:
#         gl_d = Game_list.get(Game_list.id == i)
#         gl_d.delete_instance()
#     results = Result.select().where((Result.title_id == self) & (Result.system_id == id_system))
#     for i in results:
#         r_d = Result.get(Result.id == i)
#         r_d.delete_instance()
#     choice = Choice.select().where(Choice.title_id == self)
#     for i in choice:
#         if stage == "Квалификация":
#             Choice.update(group = None, posev_group=None).where(Choice.id == i).execute()
#         else:
#             Choice.update(final = None, posev_final=None).where(Choice.id == i).execute()

def clear_db_before_choice(title_id, sex, stage="Квалификация"):
    system = System.get_or_none(
        (System.stage == stage) &
        (System.title_id == title_id) &
        (System.sex == sex)
    )
    if not system:
        return
    Game_list.delete().where(
        (Game_list.title_id == title_id) &
        (Game_list.system_id == system.id)
    ).execute()
    Result.delete().where(
        (Result.title_id == title_id) &
        (Result.system_id == system.id)
    ).execute()
    Choice.update(group=None, posev_group=None).where(
        (Choice.title_id == title_id) &
        (Choice.sex == sex)
    ).execute()
    system.choice_flag = False
    system.save()



# def choice_group_manual(self, athletes, num_groups, stage, parent=None):
#     """
#     Функция для вызова ручной жеребьевки
    
#     Args:
#         athletes: список списков [id игрока, фамилия_имя, рейтинг, регион, тренер]
#         num_groups: количество групп (от 2 до 32)
#         parent: родительское окно
    
#     Returns:
#         list: список результатов или None если отмена
#     """

#     existing_data = None
#     if num_groups == 1:
#         system = System.select().where((System.title_id == self.current_title_id) and (System.stage == stage)).get()  # находит system id последнего

#     elif num_groups > 1 or num_groups <= 48:
#     #     raise ValueError("Количество групп должно быть от 2 до 32")
#         system = System.select().where((System.title_id == self.current_title_id) and (System.stage == stage)).get()  # находит system id последнего

#     check_flag = system.choice_flag

#     if check_flag is True:
#         # Проверяем, есть ли уже жеребьевка в базе данных
#         existing_data = load_existing_draw_from_db(self.current_title_id, self.current_sex)
    
#     if existing_data:
#         # Создаем диалог выбора действия
#         action_dialog = ChoiceActionDialog(parent)
#         result = action_dialog.exec_()
        
#         if result == 1:  # Сбросить
#             # Очищаем таблицу в БД
#             clear_db_before_choice(self.current_title_id, stage)
#             try:
#                 existing_data = None
#                 QMessageBox.information(parent, "Информация", 
#                     "Начинаем новую жеребьевку. Предыдущие данные удалены.")
#             except Exception as e:
#                 QMessageBox.warning(parent, "Ошибка", f"Ошибка при очистке БД: {str(e)}")
#                 return None
#         elif result == 2:  # Загрузить
#             # Загружаем существующую жеребьевку
#             pass
#         else:  # Отмена
#             return None
    
#     dialog = ChoiceGroupManual(
#             athletes, num_groups,
#             self.current_title_id,
#             self.current_sex,
#             parent=parent,
#             existing_data=existing_data,
#         )
#     result_code = dialog.exec_()
    
#     if result_code == QDialog.Accepted:
#         return dialog.get_results()
  
#     else:
#         return None

def choice_group_manual(self, athletes, num_groups, stage, parent=None):
    existing_data = None
    system = System.get_or_none(
        (System.title_id == self.current_title_id) &
        (System.sex == self.current_sex) &
        (System.stage == stage)
    )
    if system is None:
        # создадим систему квалификации, если её ещё нет
        system = System.create(
            title_id=self.current_title_id,
            sex=self.current_sex,
            stage=stage,
            total_group=num_groups,
            max_player=(len(athletes) + num_groups - 1) // num_groups,
            type_table="Круговая",
            score_flag=5,
        )

    if system.choice_flag:
        existing_data = load_existing_draw_from_db(
            self.current_title_id, self.current_sex, stage
        )

    if existing_data:
        action_dialog = ChoiceActionDialog(parent)
        result = action_dialog.exec_()
        if result == 1:       # Сбросить
            clear_db_before_choice(self.current_title_id, self.current_sex, stage)
            existing_data = None
            QMessageBox.information(
                parent, "Информация",
                "Начинаем новую жеребьевку. Предыдущие данные удалены."
            )
        elif result == 2:     # Загрузить
            pass
        else:
            return None

    dialog = ChoiceGroupManual(
        athletes, num_groups,
        self.current_title_id,
        self.current_sex,
        parent=parent,
        existing_data=existing_data,
    )
    if dialog.exec_() == QDialog.Accepted:
        return dialog.get_results()
    return None

# ========== РУЧНАЯ ЖЕРЕБЬЁВКА ПОЛУФИНАЛОВ (ОБНОВЛЁННАЯ) ==========
class SemiFinalManual(QDialog):
    """
    Диалог ручной жеребьёвки полуфиналов.
    Автоматически заполняет 1-е и 2-е места из квалификационных групп.
    3-и и 4-е места распределяются вручную из списка, отсортированного
    от второй половины групп к первой.
    """
    import time

    def __init__(self, athletes, groups_data, title_id=None, parent=None,
            current_sex=None, main_window=None):          # <-- NEW параметр
        super().__init__(parent)
        self._last_placed = None    # (g_idx, row, timestamp)
        self.athletes = athletes
        self.groups_data = groups_data
        self.main_window = main_window 
        self.title_id = title_id
        self.current_title_id = title_id                                    # NEW
        self.current_sex = current_sex or getattr(parent, 'current_sex', None) or "man"  # NEW
        self.num_sf = 2                         # количество полуфиналов
        self.current_sf = 0                     # 0 - первый, 1 - второй
        self.players_per_group = 4              # в группе полуфинала 4 места

        # Данные полуфиналов
        self.sf_groups = []                     # для каждого полуфинала список групп (каждая группа - список из 4 элементов)
        self.available_players = []             # для каждого полуфинала список доступных игроков (кортежи (группа_квалиф, игрок))
        self.current_player_idx = 0             # индекс следующего игрока в списке

        self.conflicts = []                     # для сбора конфликтов
        self.initUI()
        self.prepare_data()
       
        self.update_interface()
   
    def prepare_data(self):
        """SF1 = 1-2 места, SF2 = 3-4 места квалификации.

        Авто: QG1..QG(half) → позиции 0,1 в SF-группах (по номеру QG).
        Ручной список: QG(half+1)..QG(total) — ВОЗРАСТАНИЕ (17..32 при 32 группах).
        Жеребьёвка ручная идёт с последней SF-группы к первой:
        - SF-группа №(half)   (QG half)  ← первые два игрока из списка (QG half+1)
        - SF-группа №(half-1) (QG half-1)← следующие два (QG half+2)
        - …
        - SF-группа №1        (QG 1)     ← последние два (QG total)
        Итог: пары (1↔32, 2↔31, …, 16↔17).
        """
        total_qual_groups = len(self.groups_data)      # 32
        half = total_qual_groups // 2                  # 16
        num_sf_groups = half

        self.sf_groups = [
            [[None, None, None, None] for _ in range(num_sf_groups)]
            for _ in range(2)
        ]

        by_group = {g: players for g, players in self.groups_data}

        # Авто — первая половина QG
        for qg in range(1, half + 1):
            sf_g = qg - 1
            pl = by_group.get(qg, [])

            if len(pl) >= 1 and pl[0] is not None:
                self.sf_groups[0][sf_g][0] = pl[0]   # SF1, 1-е место
            if len(pl) >= 2 and pl[1] is not None:
                self.sf_groups[0][sf_g][1] = pl[1]   # SF1, 2-е место
            if len(pl) >= 3 and pl[2] is not None:
                self.sf_groups[1][sf_g][0] = pl[2]   # SF2, 3-е место
            if len(pl) >= 4 and pl[3] is not None:
                self.sf_groups[1][sf_g][1] = pl[3]   # SF2, 4-е место

        # Ручной список: возрастание 17..32
        manual_sf0, manual_sf1 = [], []
        for qg in range(half + 1, total_qual_groups + 1):
            pl = by_group.get(qg, [])
            if len(pl) >= 1 and pl[0] is not None:
                manual_sf0.append((qg, pl[0]))
            if len(pl) >= 2 and pl[1] is not None:
                manual_sf0.append((qg, pl[1]))
            if len(pl) >= 3 and pl[2] is not None:
                manual_sf1.append((qg, pl[2]))
            if len(pl) >= 4 and pl[3] is not None:
                manual_sf1.append((qg, pl[3]))

        self.available_players = [manual_sf0, manual_sf1]
        self.current_player_idx = 0

        # убрать всех, кто уже стоит в авто-позициях 1-2
        for sf in (0, 1):
            self._clean_pool(sf)

    def initUI(self):
        self.setWindowTitle('Ручная жеребьёвка полуфиналов')
        self.resize(1300, 750)
        self.setMinimumSize(1100, 650)
        main_layout = QVBoxLayout(self)

        # Верхняя панель: SF-селектор + статус
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Полуфинал:"))
        self.sf_combo = QComboBox()
        self.sf_combo.addItems([
            "Полуфинал 1 (1-е и 2-е места квалификации)",
            "Полуфинал 2 (3-е и 4-е места квалификации)",
        ])
        self.sf_combo.currentIndexChanged.connect(self.on_sf_changed)
        top_layout.addWidget(self.sf_combo)

        self.current_player_label = QLabel("Текущий игрок: -")
        top_layout.addWidget(self.current_player_label, stretch=1)
        self.current_sf_label = QLabel("Полуфинал: 1")
        top_layout.addWidget(self.current_sf_label)
        main_layout.addLayout(top_layout)

        # Основная часть: слева список игроков, справа таблицы групп
        content_layout = QHBoxLayout()

        # Левая панель – список доступных игроков
        left_panel = QFrame()
        left_panel.setMaximumWidth(350)
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("Доступные игроки:"))
        self.players_list = QListWidget()
        self.players_list.setAlternatingRowColors(True)
        self.players_list.itemDoubleClicked.connect(self.on_player_double_click)
        left_layout.addWidget(self.players_list)
        content_layout.addWidget(left_panel)

        # Правая панель – группы полуфинала
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        self.groups_scroll = QScrollArea()
        self.groups_scroll.setWidgetResizable(True)
        self.groups_widget = QWidget()
        self.groups_layout = QGridLayout(self.groups_widget)
        self.groups_layout.setAlignment(Qt.AlignTop)
        self.groups_scroll.setWidget(self.groups_widget)
        right_layout.addWidget(self.groups_scroll)
        content_layout.addWidget(right_panel, stretch=1)
        main_layout.addLayout(content_layout)

        # Кнопки управления
        btn_layout = QHBoxLayout()
        self.btn_reset = QPushButton("Сбросить текущий")
        self.btn_reset.clicked.connect(self.reset_current_sf)
        btn_layout.addWidget(self.btn_reset)
        self.btn_auto_fill = QPushButton("Авто-заполнить 3-4 места")
        self.btn_auto_fill.clicked.connect(self.auto_fill_remaining)
        btn_layout.addWidget(self.btn_auto_fill)
        self.btn_save = QPushButton("Записать результаты")
        self.btn_save.clicked.connect(self.save_results)
        btn_layout.addWidget(self.btn_save)
        self.btn_close = QPushButton("Закрыть")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)
        main_layout.addLayout(btn_layout)

        # в initUI, в btn_layout (или отдельной строкой после btn_layout):
        self.btn_fullscreen = QPushButton("⛶ Полный экран (F11)")
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        main_layout.addWidget(self.btn_fullscreen)

        # горячие клавиши
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)
        QShortcut(QKeySequence("Esc"), self, activated=self._on_escape)

        # в __init__ перед initUI():
        self.is_fullscreen = False
        self._saved_geometry = None

        self.setModal(True)

    def on_sf_changed(self, idx):
        if not self.sf_combo.signalsBlocked() and idx == self.current_sf:
            return   # программный setCurrentIndex — ничего не делаем
        self.current_sf = idx
        self.current_player_idx = 0
        self.update_interface()
 
    def _on_escape(self):
        if self.is_fullscreen:
            self.toggle_fullscreen()
        else:
            self.reject()

    def toggle_fullscreen(self):
        if self.is_fullscreen:
            if self._saved_geometry is not None:
                self.setGeometry(self._saved_geometry)
            self.showNormal()
            self.is_fullscreen = False
            self.btn_fullscreen.setText("⛶ Полный экран (F11)")
        else:
            self._saved_geometry = self.geometry()
            self.showFullScreen()
            self.is_fullscreen = True
            self.btn_fullscreen.setText("⤡ Выйти из полного экрана (F11)")
        # перестроить таблицы под новый размер
        self.update_groups_tables()

    def _region_conflict_at(self, group, row, athlete):
        """Конфликт региона: только 1-е (idx 0) и 3-е (idx 2) места."""
        if row != 2:
            return False
        first = group[0] if len(group) > 0 else None
        return bool(first and athlete and first[3] == athlete[3])

    def update_interface(self):
        self.sf_combo.blockSignals(True)
        self.sf_combo.setCurrentIndex(self.current_sf)
        self.sf_combo.blockSignals(False)
        self.update_players_list()
        self.update_groups_tables()
        self.current_sf_label.setText(f"Полуфинал: {self.current_sf + 1}")

        players = self.available_players[self.current_sf]
        if self.current_player_idx < len(players):
            qg, p = players[self.current_player_idx]
            expected_sf_group = len(players) // 2 - self.current_player_idx // 2
            self.current_player_label.setText(
                f"Следующий: {p[1]} (R {p[2]}, регион {p[3]}, из Гр.{qg}) "
                f"— ожидается группа №{expected_sf_group} "
                f"(осталось {len(players) - self.current_player_idx})"
            )
        else:
            self.current_player_label.setText("Все игроки распределены!")

    def update_players_list(self):
        self.players_list.clear()
        if not self.available_players:
            return
        players = self.available_players[self.current_sf] or []

        for i in range(self.current_player_idx, len(players)):
            entry = players[i]
            qg, athlete = entry if isinstance(entry, (tuple, list)) and len(entry) == 2 else ("?", entry)
            if isinstance(athlete, dict):
                athlete = athlete.get("player")
            if not athlete or len(athlete) < 4:
                self.players_list.addItem(f"!! {entry!r}")
                continue

            name   = athlete[1] or "—"
            region = athlete[3] or "—"
            sf_grp = self._find_sf_group(athlete)
            sf_part = f"SF{sf_grp}, " if sf_grp else ""
            self.players_list.addItem(f"{sf_part}гр. {qg}, {name}, {region}")
    
    def update_groups_tables(self):
        
        for i in reversed(range(self.groups_layout.count())):
            w = self.groups_layout.itemAt(i).widget()
            if w:
                w.deleteLater()

        groups   = self.sf_groups[self.current_sf]
        total_qg = len(self.groups_data)
        half     = total_qg // 2
        cols     = 4

        # Обратный порядок отображения: SF-группа half, half-1, …, 1
        ordered = list(enumerate(groups))[::-1]   # [(15, gr16), (14, gr15), …, (0, gr1)]

        for pos, (g_idx, group) in enumerate(ordered):
            low_qg  = g_idx + 1            # 1..16
            high_qg = total_qg - g_idx     # 32..17

            frame = QFrame()
            frame.setFrameStyle(QFrame.Box)
            frame.setMaximumWidth(320 if not self.is_fullscreen else 16777215)
            frame.setMinimumWidth(220 if not self.is_fullscreen else 300)
            frame_layout = QVBoxLayout(frame)

            header = QLabel(f"Группа {g_idx + 1} (Гр.{low_qg} + Гр.{high_qg})")
            header.setStyleSheet(
                "font-weight: bold; background-color: #4CAF50; color: white; padding: 3px;"
            )
            header.setAlignment(Qt.AlignCenter)
            frame_layout.addWidget(header)

            table = QTableWidget()
            table.setColumnCount(2)
            table.setHorizontalHeaderLabels(["№", "Игрок"])
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
            table.setColumnWidth(0, 40)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            table.setRowCount(self.players_per_group)
            table.verticalHeader().setVisible(False)
            table.setAlternatingRowColors(True)
            table.setProperty("group_idx", g_idx)        # <-- реальный индекс!
            table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            # update_groups_tables:
            table.setEditTriggers(QTableWidget.NoEditTriggers)
            table.cellClicked.connect(self.on_cell_clicked)
            table.itemDoubleClicked.connect(self.on_item_double_clicked)

            for row in range(self.players_per_group):
                num_item = QTableWidgetItem(str(row + 1))
                num_item.setTextAlignment(Qt.AlignCenter)
                num_item.setFlags(num_item.flags() & ~Qt.ItemIsEditable)
                table.setItem(row, 0, num_item)

                athlete = group[row] if row < len(group) else None
                if athlete:
                    item = QTableWidgetItem(f"{athlete[1]} ({athlete[3]}) R:{athlete[2]}")
                    item.setData(Qt.UserRole, athlete[0])
                    table.setItem(row, 1, item)
                else:
                    table.setItem(row, 1, QTableWidgetItem(""))

                frame_layout.addWidget(table)
                row_pos = pos // cols
                col_pos = pos % cols
                self.groups_layout.addWidget(frame, row_pos, col_pos)

                # Регион игрока, которого сейчас сеем
                pool = self.available_players[self.current_sf]
                current_region = None
                if self.current_player_idx < len(pool):
                    entry = pool[self.current_player_idx][1]
                    athlete = entry['player'] if isinstance(entry, dict) else entry
                    if athlete:
                        current_region = athlete[3]

                # ... внутри цикла, после заполнения ячеек ...

                # Подсветка «своего» региона ТОЛЬКО у 1-го места (позиция 0)
                if current_region and group and group[0] and group[0][3] == current_region:
                    item = table.item(0, 1)
                    if item:
                        item.setBackground(QBrush(QColor(255, 255, 150)))   # жёлтый

                # Красная подсветка конфликта 1↔3 — как было (перекрывает жёлтую)
                first = group[0] if len(group) > 0 else None
                if first and len(group) > 2 and group[2] and group[2][3] == first[3]:
                    item = table.item(2, 1)
                    if item:
                        item.setBackground(QBrush(QColor(255, 200, 200)))
                    header.setStyleSheet(
                        "font-weight: bold; background-color: #f44336; color: white; padding: 3px;"
                    )
                    header.setToolTip(f"Конфликт региона «{first[3]}»: 1-е и 3-е места.")

        for c in range(cols):
            self.groups_layout.setColumnStretch(c, 1)

    def on_player_double_click(self, item):
        """Двойной клик по игроку в списке - размещает его в следующую свободную ячейку."""
        # Аналогично клику по ячейке, но используем текущего игрока
        # Найдём первую свободную ячейку (3-ю или 4-ю позицию) в группах текущего полуфинала
        groups = self.sf_groups[self.current_sf]
        for g_idx, group in enumerate(groups):
            for row in range(2, self.players_per_group):  # только 3-я и 4-я
                if len(group) <= row or group[row] is None:
                    self.place_player_to_cell(g_idx, row)
                    return
        QMessageBox.information(self, "Информация", "Нет свободных ячеек для размещения!")

    def on_item_double_clicked(self, item):
        if item.column() != 1:
            return

        table = item.tableWidget()
        g_idx = table.property("group_idx")
        if g_idx is None:
            return
        row = item.row()

        lp = self._last_placed
        if lp and lp[0] == g_idx and lp[1] == row and (time.time() - lp[2]) < 0.5:
            return

        if row < 2:
            QMessageBox.information(
                self, "Информация",
                "1-е и 2-е места заполняются автоматически и не снимаются."
            )
            return

        groups = self.sf_groups[self.current_sf]
        if g_idx >= len(groups):
            return
        group = groups[g_idx]

        pair = [(pos, group[pos]) for pos in (2, 3)
                if len(group) > pos and group[pos] is not None]
        if not pair:
            return

        names = ", ".join(a[1] for _, a in pair)
        if QMessageBox.question(
            self, "Снять пару",
            f"Убрать из группы {g_idx + 1} пару: {names}?\n\n"
            f"Игроки вернутся в список доступных.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        ) != QMessageBox.Yes:
            return

        to_pool = []
        for pos, athlete in pair:
            qg = self._find_qual_group(athlete)
            group[pos] = None
            if qg is not None:
                to_pool.append((qg, athlete))

        self._return_to_pool(self.current_sf, to_pool)
        self._clean_pool(self.current_sf)   # страховка: убрать случайные дубли/уже размещённых

        self.current_player_idx = 0
        self._last_placed = None
        self.update_interface()
    
    def on_cell_clicked(self, row, col):
        if col != 1:
            return

        table = self.sender()
        if not table:
            return
        g_idx = table.property("group_idx")
        if g_idx is None:
            return

        if row < 2:
            QMessageBox.warning(self, "Ошибка",
                                "1-е и 2-е места заполняются автоматически!")
            return
        if row == 3:
            # 4-е место заполняется автоматически партнёром
            if len(groups[g_idx]) > 2 and groups[g_idx][2] is not None:
                QMessageBox.information(
                    self, "Информация",
                    "4-е место заполняется автоматически парой к 3-му.\n"
                    "Чтобы поставить сюда другого игрока, сначала снимите пару "
                    "двойным кликом."
                )
                return
        # ГЛАВНОЕ: занятая ячейка — молча выходим.
        groups = self.sf_groups[self.current_sf]
        if (g_idx < len(groups)
                and row < len(groups[g_idx])
                and groups[g_idx][row] is not None):
            return   # <-- снятие делает on_item_double_clicked

        if self.place_player_to_cell(g_idx, row):
            # защита от «двойного клика по пустой»
            import time
            self._last_placed = (g_idx, row, time.time())

    def place_player_to_cell(self, group_idx, row):
        """Ставит следующего игрока на (group_idx, row) и, если row==2,
        автоматически подставляет партнёра из того же QG на 4-е место.
        Возвращает True/False.
        """
        if row not in (2, 3):
            return False

        pool = self.available_players[self.current_sf]
        if self.current_player_idx >= len(pool):
            QMessageBox.information(self, "Информация", "Нет доступных игроков!")
            return False

        groups = self.sf_groups[self.current_sf]
        group = groups[group_idx]

        if len(group) > row and group[row] is not None:
            return False

        qual_group, athlete = pool[self.current_player_idx]
        if isinstance(athlete, dict):
            athlete = athlete['player']

        # Конфликт региона 1↔3 — только для row == 2
        if self._region_conflict_at(group, row, athlete):
            reply = QMessageBox.question(
                self, 'Конфликт регионов',
                f'В группе уже есть игрок из региона {athlete[3]} на 1-м месте.\n'
                f'Всё равно разместить {athlete[1]} на 3-е место?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.No:
                return False

        # 1) ставим
        while len(group) <= row:
            group.append(None)
        group[row] = athlete

        # 2) сразу удаляем его из пула
        athlete_id = self._pid(athlete)
        for idx, (q, p) in enumerate(pool):
            if self._pid(p) == athlete_id and q == qual_group:
                del pool[idx]
                break

        # 3) если это 3-я позиция — ищем партнёра из того же QG и ставим на 4-ю
        if row == 2:
            partner_idx = 1 if self.current_sf == 0 else 3
            partner = None
            for qg, players_list in self.groups_data:
                if qg == qual_group:
                    if partner_idx < len(players_list):
                        partner = players_list[partner_idx]
                    break

            if partner is not None:
                partner_id = self._pid(partner)
                # не ставим, если партнёр уже где-то в текущем SF
                if partner_id not in self._placed_ids(self.current_sf):
                    # и должен быть в пуле
                    for idx, (q, p) in enumerate(pool):
                        if self._pid(p) == partner_id and q == qual_group:
                            del pool[idx]
                            break
                    # ставим на 4-ю
                    while len(group) <= 3:
                        group.append(None)
                    if group[3] is None:
                        group[3] = partner

        # 4) страховка: чистим пул от уже размещённых и дублей
        self._clean_pool(self.current_sf)

        # 5) индекс всегда = длина пула - оставшиеся? Нет: индекс — «следующий».
        #    Если он ушёл за границу, подрежем (в _clean_pool это уже есть).
        if self.current_player_idx > len(self.available_players[self.current_sf]):
            self.current_player_idx = len(self.available_players[self.current_sf])

        self.update_interface()

        if not self.available_players[self.current_sf]:
            QMessageBox.information(self, "Завершено", "Все игроки распределены!")

        return True

    def _find_qual_group(self, athlete):
        """Номер квалификационной группы, откуда пришёл игрок."""
        aid = athlete[0]
        for qg, players in self.groups_data:
            for entry in players:
                pl = entry['player'] if isinstance(entry, dict) else entry
                if pl and pl[0] == aid:
                    return qg
        return None

    def _find_sf_group(self, athlete):
        """Номер SF-группы (1..16) текущего полуфинала, где сейчас стоит игрок."""
        aid = self._pid(athlete)
        groups = self.sf_groups[self.current_sf]
        for g_idx, g in enumerate(groups):
            if any(self._pid(a) == aid for a in g if a):
                return g_idx + 1
        return None

    def _pid(self, athlete):
        """ID игрока в любом формате записи (list / tuple / dict)."""
        if athlete is None:
            return None
        if isinstance(athlete, dict):
            # {'place':…, 'player': […]}
            pl = athlete.get('player')
            return pl[0] if pl else None
        return athlete[0]

    def _pool_has(self, sf, athlete):
        aid = self._pid(athlete)
        return any(self._pid(p) == aid for _q, p in self.available_players[sf])

    def _return_to_pool(self, sf, entries):
        pool = self.available_players[sf]
        placed = self._placed_ids(sf)
        existing = {self._pid(p) for _q, p in pool}

        for qg, athlete in entries:
            aid = self._pid(athlete)
            if aid is None:
                continue
            # уже где-то стоит в группе — не возвращаем
            if aid in placed:
                continue
            # уже есть в пуле — пропускаем дубль
            if aid in existing:
                continue
            pool.append((qg, athlete))
            existing.add(aid)

        pool.sort(key=lambda x: x[0])

    def _placed_ids(self, sf=None):
        """Множество ID всех игроков, которые сейчас размещены в sf_groups[sf]."""
        sf = self.current_sf if sf is None else sf
        ids = set()
        for group in self.sf_groups[sf]:
            for a in group:
                if a:
                    aid = self._pid(a)
                    if aid is not None:
                        ids.add(aid)
        return ids

    def _clean_pool(self, sf=None):
        """Удаляет из available_players[sf] всех, кто уже размещён в группах,
        и дубли по ID. Сохраняет порядок QG."""
        sf = self.current_sf if sf is None else sf
        placed = self._placed_ids(sf)
        seen = set()
        cleaned = []
        for qg, athlete in self.available_players[sf]:
            aid = self._pid(athlete)
            if aid is None:
                continue
            if aid in placed or aid in seen:
                continue
            seen.add(aid)
            cleaned.append((qg, athlete))
        cleaned.sort(key=lambda x: x[0])
        self.available_players[sf] = cleaned

        # подрезать индекс, если он ушёл за границу
        if self.current_player_idx > len(cleaned):
            self.current_player_idx = len(cleaned)

    def reset_current_sf(self):
        if QMessageBox.question(
            self, 'Сброс',
            'Очистить все 3-и и 4-е места текущего полуфинала?\n\n'
            'Игроки вернутся в список доступных.',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        ) != QMessageBox.Yes:
            return

        groups = self.sf_groups[self.current_sf]
        to_pool = []
        for g in groups:
            for pos in (2, 3):
                if len(g) > pos and g[pos] is not None:
                    athlete = g[pos]
                    qg = self._find_qual_group(athlete)
                    g[pos] = None
                    if qg is not None:
                        to_pool.append((qg, athlete))

        self._return_to_pool(self.current_sf, to_pool)
        self._clean_pool(self.current_sf)   # страховка: убрать случайные дубли/уже размещённых
        self.current_player_idx = 0
        self._last_placed = None
        self.update_interface()
    
    def auto_fill_remaining(self):
        """Автоматически заполняет все оставшиеся 3-и и 4-е места (без ручного выбора)."""
        # Просто последовательно размещаем всех доступных игроков
        groups = self.sf_groups[self.current_sf]
        players = self.available_players[self.current_sf]
        idx = self.current_player_idx
        for g_idx, group in enumerate(groups):
            for row in range(2, self.players_per_group):
                if idx >= len(players):
                    break
                if len(group) <= row or group[row] is None:
                    qual_group, athlete = players[idx]
                    if self._region_conflict_at(group, row, athlete):
                        self.conflicts.append(
                            f"Конфликт региона (1↔3): {athlete[1]} в группе {g_idx+1}"
                        )
                    while len(group) <= row:
                        group.append(None)
                    group[row] = athlete
                    idx += 1
                    if row == 2:
                        partner = None
                        for qg, pl in self.groups_data:
                            if qg == qual_group:
                                if len(pl) >= 4:
                                    partner = pl[3]
                                break
                        if partner:
                            if len(group) <= 3 or group[3] is None:
                                group[3] = partner   # без проверки конфликта
                                for i, (q, p) in enumerate(players):
                                    if p[0] == partner[0] and q == qual_group:
                                        del players[i]
                                        if i < idx:
                                            idx -= 1
                                        break
                            if idx >= len(players):
                                break
        self.current_player_idx = idx
        self.update_interface()
        if self.conflicts:
            QMessageBox.warning(self, "Конфликты", "\n".join(self.conflicts))
            self.conflicts = []

    def save_results(self):
        """Сохранение результатов ручной жеребьёвки полуфиналов.

        Для каждого полуфинала:
        1) создаёт/находит System (с sex);
        2) чистит Game_list и старые Result этой системы;
        3) заполняет Choice (semi_final/posev_sf/sf_group) и Game_list;
        4) вызывает create_matches_for_semi_final — с переносом данных
            из квалификации для повторившихся пар;
        5) ставит choice_flag.
        """
        title_id = self.current_title_id
        sex = self.current_sex

        try:
            for sf_idx, groups in enumerate(self.sf_groups):
                sf_num = sf_idx + 1
                stage = ("Квалификация. 1-й полуфинал" if sf_idx == 0
                        else "Квалификация. 2-й полуфинал")

                # --- 1. System ---
                system = System.get_or_none(
                    (System.title_id == title_id) &
                    (System.sex == sex) &
                    (System.stage == stage)
                )
                if not system:
                    system = System.create(
                        title_id=title_id,
                        sex=sex,
                        stage=stage,
                        total_group=len(groups),
                        max_player=4,
                        type_table="Круговая",
                        score_flag=5,
                    )
                elif not getattr(system, "sex", None):
                    system.sex = sex
                    system.save()

                # --- 2. Очистка ---
                Game_list.delete().where(
                    (Game_list.title_id == title_id) &
                    (Game_list.system_id == system.id)
                ).execute()

                Result.delete().where(
                    (Result.title_id == title_id) &
                    (Result.system_stage == stage) &
                    (Result.sex == sex)
                ).execute()

                player_ids = [a[0] for g in groups for a in g if a]
                if player_ids:
                    Choice.update(
                        semi_final=None, posev_sf=None, sf_group=None
                    ).where(Choice.player_choice_id.in_(player_ids)).execute()

                # --- 3. Choice + Game_list + сборка sf_groups для create_matches ---
                sf_groups_for_matches = []
                for g_idx, group in enumerate(groups):
                    gr_num = g_idx + 1
                    choice_objs = []
                    for pos, athlete in enumerate(group, start=1):
                        if not athlete:
                            continue

                        choice = Choice.get_or_none(
                            (Choice.title_id == title_id) &
                            (Choice.player_choice_id == athlete[0])
                        )
                        if not choice:
                            continue

                        choice.semi_final = sf_num
                        choice.posev_sf = pos
                        choice.sf_group = f"{gr_num} группа"
                        choice.save()

                        Game_list.create(
                            number_group=f"{gr_num} группа",
                            rank_num_player=pos,
                            player_group=athlete[0],
                            system_id=system.id,
                            title_id=title_id,
                            player_double_id=None,
                            team_id=None,
                            sex=sex,
                        )

                        choice_objs.append(choice)

                    sf_groups_for_matches.append({
                        'sf_group_num': gr_num,
                        'players': choice_objs,
                    })

                # --- 4. Result-матчи с переносом из квалификации ---
                self.main_window.create_matches_for_semi_final(sf_num, sf_groups_for_matches, stage)

                # --- 5. Флаг ---
                self.set_choice_flag_for_stage(stage, flag=1)

            QMessageBox.information(
                self, "Успех",
                "Результаты обоих полуфиналов сохранены "
                "(с переносом данных из квалификации для повторившихся пар)."
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Ошибка", f"Ошибка сохранения: {str(e)}")

    def set_choice_flag_for_stage(self, stage, flag):
        try:
            system = System.get(
                (System.title_id == self.current_title_id) &
                (System.sex == self.current_sex) &
                (System.stage == stage)
            )
            system.choice_flag = flag
            system.save()
        except Exception as e:
            print(f"Ошибка установки флага: {e}")
# ========== ФУНКЦИИ ВЫЗОВА ==========
def choice_semifinal_manual(self, stage, parent=None):
    """
    Запускает ручную жеребьёвку полуфиналов.
    Собирает данные из квалификационных групп и открывает диалог.
    """
    if stage == "Квалификация. 1-й полуфинал":
        place_list = [1, 2]
    else:
        place_list = [3, 4]

    try:
        # Получаем систему квалификации
        system = System.get(
            (System.title_id == self.current_title_id) &
            (System.sex == self.current_sex) &
            (System.stage == "Квалификация")
        )
        # Собираем данные по группам
        groups_data = []
        for gr_num in range(1, system.total_group + 1):
            choices = Choice.select().where(
                (Choice.title_id == self.current_title_id) &
                (Choice.sex == self.current_sex) &
                (Choice.group == f"{gr_num} группа") &
                (Choice.mesto_group.in_(place_list))
            ).order_by(Choice.group, Choice.mesto_group)
            athletes_in_group = []

            for ch in choices:
                player = Player.get_or_none(Player.id == ch.player_choice_id)
                if player:
                    athletes_in_group.append(
                        [player.id, player.fio, player.rank, player.region, player.coach_id]
                    )
            groups_data.append((gr_num, athletes_in_group))


        # Получаем всех спортсменов турнира (для справки)
        all_athletes = []
        for player in Player.select().where(
            (Player.title_id == self.current_title_id) &
              (Player.sex == self.current_sex)
            ):
            all_athletes.append([player.id, player.fio, player.rank, player.region, player.coach_id])

        dialog = SemiFinalManual(all_athletes, groups_data, self.current_title_id, parent,
            current_sex=self.current_sex, main_window=self
            )
        return dialog.exec_() == QDialog.Accepted
    except Exception as e:
        QMessageBox.warning(parent, "Ошибка", f"Ошибка подготовки данных: {str(e)}")
        return False
# вариант игрок город
def get_player_fio_city(self, player_id):
    player = Player.get_or_none(Player.id == player_id)
    if not player:
        return f"ID{player_id}"
    return f"{player.fio} ({player.region})"
# ===============
def choice_semifinal(self, title_id, parent=None):
    """
    Главная функция выбора типа жеребьёвки полуфиналов.
    Предлагает автоматическую или ручную.
    """
    # Проверяем, есть ли квалификация
    try:
        system = System.get(
            (System.title_id == title_id) &
            (System.sex == self.current_sex) &
            (System.stage == "Квалификация")
        )
    except:
        QMessageBox.warning(parent, "Ошибка", "Сначала проведите жеребьёвку квалификационных групп!")
        return False

    # Проверяем, есть ли игроки в группах
    if not Choice.select().where((Choice.title_id == title_id) & (System.sex == self.current_sex)).exists():
        QMessageBox.warning(parent, "Ошибка", "Нет данных о распределении игроков по группам квалификации!")
        return False

    # Диалог выбора
    from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout

    class ChoiceDialog(QDialog):
        def __init__(self):
            super().__init__(parent)
            self.setWindowTitle("Жеребьёвка полуфиналов")
            self.setModal(True)
            self.setFixedSize(400, 200)
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel("Выберите способ жеребьёвки полуфиналов:"))
            btn_layout = QHBoxLayout()
            btn_auto = QPushButton("Автоматическая")
            btn_auto.clicked.connect(lambda: self.done(1))
            btn_manual = QPushButton("Ручная")
            btn_manual.clicked.connect(lambda: self.done(2))
            btn_cancel = QPushButton("Отмена")
            btn_cancel.clicked.connect(lambda: self.done(0))
            btn_layout.addWidget(btn_auto)
            btn_layout.addWidget(btn_manual)
            btn_layout.addWidget(btn_cancel)
            layout.addLayout(btn_layout)

    choice_dlg = ChoiceDialog()
    result = choice_dlg.exec_()

    if result == 1:  # Автоматическая
        # Вызываем существующую функцию автоматической жеребьёвки (create_semi_final_1)
        return self.create_semi_final_1(1, system.total_group) is not None
    elif result == 2:  # Ручная
        return choice_semifinal_manual(self, title_id, parent)
    else:
        return False    

class PlayerItem(QListWidgetItem):
    """Элемент списка игроков с дополнительными данными"""
    def __init__(self, player_data):
        super().__init__()
        self.player_data = player_data
        self.setText(f"{player_data['name']} ({player_data['city']})")

class ManualNetDrawDialog(QDialog):
    def __init__(self, parent=None, title_id=None, stage_name=None, sex=None):
        super().__init__(parent)
        self.parent = parent
        self.title_id = title_id
        self.stage_name = stage_name
        self.sex = sex
        self.current_system = None
        self.current_player = None
        self.players = []
        self.players_copy = []
        self.net_positions = {}
        self.max_players = 0
        self.all_players = []  # полный список для подсветки посева
        self.setWindowTitle(f"Ручная жеребьевка - {stage_name}")
        self.setMinimumSize(1000, 850)
        self.setModal(True)
        self.init_ui()
        self.load_stage_data()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Верхняя панель
        top_panel = QHBoxLayout()
        top_panel.addWidget(QLabel(f"Этап: {self.stage_name}"))
        top_panel.addStretch()
        self.status_label = QLabel("Загрузка данных...")
        self.status_label.setStyleSheet("padding: 5px; background-color: #FFFFE0; border-top: 1px solid #ddd; font-size: 12px;")
        top_panel.addWidget(self.status_label)
        self.save_btn = QPushButton("💾 Сохранить жеребьевку")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_drawing)
        top_panel.addWidget(self.save_btn)
        main_layout.addLayout(top_panel)

        # Основной сплиттер
        splitter = QSplitter(Qt.Horizontal)

        # Левая панель
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Информация об игроке
        info_group = QGroupBox("Текущий игрок")
        info_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                border: 2px solid #4CAF50;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                color: #4CAF50;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
            }
        """)
        info_layout = QFormLayout(info_group)
        self.player_info = {
            'name': QLabel("-"),
            'city': QLabel("-"),
            'region': QLabel("-"),
            'coach': QLabel("-"),
            'group': QLabel("-"),
        }
        info_layout.addRow("ФИО:", self.player_info['name'])
        info_layout.addRow("Город:", self.player_info['city'])
        info_layout.addRow("Регион:", self.player_info['region'])
        info_layout.addRow("Тренер:", self.player_info['coach'])
        info_layout.addRow("Группа:", self.player_info['group'])
        left_layout.addWidget(info_group)

        # Список оставшихся игроков (растягивается)
        list_group = QGroupBox("📝 Список игроков")
        list_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                border: 2px solid #2196F3;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                color: #2196F3;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
            }
        """)
        list_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        list_layout = QVBoxLayout(list_group)
        list_layout.setContentsMargins(10, 15, 10, 10)
        self.players_list = QListWidget()
        self.players_list.itemClicked.connect(self.on_list_item_clicked)
        list_layout.addWidget(self.players_list)
        left_layout.addWidget(list_group)

        splitter.addWidget(left_widget)

        # Правая панель: сетка
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.net_table = QTableWidget()
        self.net_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.net_table.setSelectionBehavior(QTableWidget.SelectItems)
        self.net_table.setAcceptDrops(True)
        self.net_table.cellClicked.connect(self.on_net_cell_clicked)
        self.net_table.setDragDropMode(QTableWidget.DropOnly)
        self.net_table.setStyleSheet("""
            QTableWidget {
                font-size: 11px;
                gridline-color: #ddd;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QTableWidget::item:selected {
                background-color: #4CAF50;
                color: white;
            }
        """)
        self.net_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_layout.addWidget(self.net_table)
        splitter.addWidget(right_widget)

        splitter.setSizes([500, 500])
        main_layout.addWidget(splitter)

    # ----------------------------------------------
    # Загрузка данных
    # ----------------------------------------------
    def load_stage_data(self):
        if not self.stage_name:
            return
        # ─── СУПЕРФИНАЛ: 1-й финал должен быть сыгран ───
        if self.stage_name == "Суперфинал" and hasattr(self.parent, '_is_stage_finished'):
            finished, played, total = self.parent._is_stage_finished("1-й финал")
            if not finished:
                QMessageBox.warning(
                    self, "Суперфинал",
                    "Нельзя провести жеребьёвку Суперфинала:\n\n"
                    "«1-й финал» ещё не сыгран полностью.\n"
                    f"Сыграно матчей: {played} из {total}.")
                self.close()
                return
            
        if self.stage_name == 'Пары':
            if self.sex == "man":
                self.stage_name = "Мужские пары"
            elif self.sex == 'woman':
                self.stage_name = "Женские пары"
            else:
                self.stage_name = "Смешанные пары"

        self.current_system = System.get_or_none(
            (System.title_id == self.title_id) &
            (System.stage == self.stage_name) &
            (System.sex == self.sex)
        )
        if not self.current_system:
            QMessageBox.warning(self, "Ошибка", f"Этап {self.stage_name} не найден")
            self.close()
            return
        # ===== мой вариант =====
        self.max_players = self.parent.get_olympic_bracket_size(self.current_system.max_player)

        # Определяем тип соревнования: пары или личное
        is_pairs = "пары" in self.stage_name.lower() or self.current_system.type_table == "Олимпийская (за 1-3 место)" and "пар" in self.stage_name.lower()

        # Проверяем, есть ли уже жеребьёвка
        existing = Game_list.select().where(
            (Game_list.title_id == self.title_id) &
            (Game_list.system_id == self.current_system.id)
        ).count()

        if existing > 0:
            self._handle_existing_drawing()
        else:
            self.draw_net()
            if is_pairs:
                self.load_players_pairs()
            else:
                self.load_players()
            self.save_btn.setEnabled(True)
            total = len(self.players) + (1 if self.current_player else 0)
            self.status_label.setText(f"Загружен этап: {self.stage_name}. Участников: {total}")

    def _handle_existing_drawing(self):
        pairs_list = ["Мужские пары", "Женские пары", "Смешанные пары"]
        is_paries = self.stage_name
        reply = QMessageBox.question(
            self,
            "Жеребьёвка уже проведена",
            "Для этого этапа уже есть жеребьёвка.\n"
            "Загрузить существующую или сбросить и начать заново?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Cancel
        )
        if reply == QMessageBox.Cancel:
            self.close()
            return
        elif reply == QMessageBox.Yes:       
            self.draw_net()
            if is_paries in pairs_list:
                self.load_players_pairs()
            else:
                self.load_players()
            self.load_existing_net()
            self.save_btn.setEnabled(True)
            self.status_label.setText(
                f"Загружена существующая жеребьёвка для {self.stage_name}"
            )
        else:
            # Сброс
            Game_list.delete().where(
                (Game_list.title_id == self.title_id) &
                (Game_list.system_id == self.current_system.id)
            ).execute()
            if is_paries in pairs_list:
                Choice_double_player.update(posev=0).where(
                    (Choice_double_player.title_id == self.title_id) &
                    (Choice_double_player.vid_para == self.sex)
                ).execute()
                self.load_players_pairs()
            else:
                Choice.update(posev_final=0).where(
                    (Choice.title_id == self.title_id) &
                    (Choice.final == self.stage_name)
                ).execute()
                self.load_players()
            self.draw_net()
            self.save_btn.setEnabled(True)
            self.status_label.setText(f"Старая жеребьёвка сброшена для {self.stage_name}")
    # ----------------------------------------------
    # Загрузка игроков
    # ----------------------------------------------
    def load_players(self):
        """Загрузка игроков для текущего финала с использованием real_place_for_final"""
        if not self.current_system:
            return

        self.players.clear()
        try:
            self.players_list.clear()
        except RuntimeError:
            self.players_list = QListWidget()

        # Получаем информацию о том, какие места выходят в этот финал
        try:
            final_info = self.parent.real_place_for_final(self.stage_name)
            # final_info должно быть словарём {'stage_exit': ..., 'place_stage': [список мест]}
            if not final_info or 'place_stage' not in final_info:
                QMessageBox.warning(self, "Ошибка", "Некорректные данные от real_place_for_final")
                return
            nums = final_info['place_stage']
            stage_exit = final_info.get('stage_exit', '')
        except AttributeError:
            QMessageBox.warning(self, "Ошибка", "Метод real_place_for_final не найден в родительском окне")
            return

        if not nums:
            QMessageBox.warning(self, "Ошибка", f"Нет мест для финала {self.stage_name}")
            return

               # Определяем поля в зависимости от источника
        if "полуфинал" in stage_exit.lower():
            semi_num = 1 if "1-й" in stage_exit else 2
            choices = Choice.select().where(
                (Choice.title_id == self.title_id) &
                (Choice.semi_final == semi_num) &
                (Choice.sex == self.sex)
            )
            group_field = 'sf_group'
            pos_field = 'posev_sf'
            place_field = 'mesto_semi_final'
        elif stage_exit and "финал" in stage_exit.lower():
            # Источник — финал (1-й, 2-й, …): игроки берутся по Choice.final
            # (используется для Суперфинала, где stage_exit = "1-й финал")
            choices = Choice.select().where(
                (Choice.title_id == self.title_id) &
                (Choice.final == stage_exit) &
                (Choice.sex == self.sex)
            )
            count = len(choices)
            group_field = 'final'
            pos_field = 'posev_final'
            place_field = 'mesto_final'
        else:
            choices = Choice.select().where(
                (Choice.title_id == self.title_id) &
                (Choice.group.contains("группа")) &
                (Choice.sex == self.sex)
            )
            group_field = 'group'
            pos_field = 'posev_group'
            place_field = 'mesto_group'

        # Собираем данные
        players_data = []
        for ch in choices:
            place = getattr(ch, place_field) or 0
            if place not in nums:
                continue
            player = Player.get_or_none(Player.id == ch.player_choice.id)
            if not player:
                continue
            group_name = getattr(ch, group_field)
            match = re.search(r'\d+', group_name)
            group_num = int(match.group()) if match else 0
            pos = getattr(ch, pos_field)

            coach_name = ""
            if player.coach_id:
                coach = Coach.get_or_none(Coach.id == player.coach_id)
                if coach:
                    coach_name = coach.coach

            players_data.append({
                'choice_id': ch.id,
                'player_id': player.id,
                'name': player.fio or player.player,
                'city': player.city or "",
                'region': player.region or "",
                'rank': player.rank or 0,
                'group': group_num,
                'position': pos,
                'place': place,
                'coach': coach_name,
                'sex': player.sex or ""
            })

        exit_count = self.current_system.mesta_exit or 1

        if self.stage_name == "1-й финал":
            # 1-й финал: сначала по месту, внутри места — по номеру группы
            players_data.sort(key=lambda x: (x['place'], x['group']))
        elif self.stage_name == "Суперфинал":
            # Суперфинал: строго по месту из 1-го финала (1, 2, 3, …, N)
            players_data.sort(key=lambda x: x['place'])
        else:
            if exit_count == 1:
                players_data.sort(key=lambda x: x['rank'], reverse=True)
            else:
                players_data.sort(key=lambda x: (x['place'], -x['rank']))

        import copy

        self.all_players = copy.deepcopy(players_data)

        # Устанавливаем текущего игрока и список оставшихся
        if players_data:
            self.current_player = players_data[0]
            self.players = players_data[1:]  # остальные игроки
            self.update_player_info(self.current_player)
            self.update_players_list()
            self.highlight_posev()
            self.highlight_conflicts(self.current_player)         
        else:
            self.current_player = None
            self.players = []
            self.update_player_info(None)

    def load_players_pairs(self):
        """Загрузка пар для текущего финала парного разряда"""
        if not self.current_system:
            return

        self.players.clear()
        try:
            self.players_list.clear()
        except RuntimeError:
            self.players_list = QListWidget()

        # Определяем источник мест для пар
        # Для парных соревнований используем реальные места из Players_double
        # либо простую логику: все пары, отсортированные по r_sum
        try:
            # Пытаемся получить информацию о местах через родительский метод
            # (если он адаптирован для пар) или используем fallback
            final_info = None
            if hasattr(self.parent, 'real_place_for_final_pairs'):
                final_info = self.parent.real_place_for_final_pairs(self.stage_name)
            elif hasattr(self.parent, 'real_place_for_final'):
                # Пробуем вызвать стандартный метод (может вернуть места для пар)
                try:
                    final_info = self.parent.real_place_for_final(self.stage_name)
                except Exception:
                    final_info = None
        except Exception as e:
            print(f"Ошибка получения данных о местах: {e}")
            final_info = None

        # Определяем список мест, которые выходят в этот финал
        if final_info and 'place_stage' in final_info:
            nums = final_info['place_stage']
            stage_exit = final_info.get('stage_exit', '')
        else:
            # Fallback: берём все пары данного вида
            nums = None
            stage_exit = ''

        # Определяем вид пары из комбобокса, если есть
        vid = "man"  # по умолчанию
        if hasattr(self.parent, 'double_vid_combo'):
            vid_text = self.parent.double_vid_combo.currentText()
            if vid_text == "мужские":
                vid = "man"
            elif vid_text == "женские":
                vid = "woman"
            elif vid_text == "смешанные":
                vid = "mix"

        # Загружаем пары из Players_double
        # query = Players_double.select().where(
        #     (Players_double.title_id == self.title_id) &
        #     (Players_double.double_vid == vid)
        # )
        query = (Players_double
         .select()
         .where(
             (Players_double.title_id == self.title_id) &
             (Players_double.double_vid == vid) &
             ~((Players_double.player_1 == "X") & (Players_double.player_2 == "X"))
         ))

        # Если есть места из final_info, фильтруем по ним (используем поле posev или r_sum)
        # Для пар обычно используются все пары, участвующие в финале
        query = query.order_by(Players_double.r_sum.desc())

        # Собираем данные пар
        players_data = []
        for double in query:
            # Формируем имя пары для отображения
            name = double.para_shot or f"{double.player_1} / {double.player_2}"
            region = double.region_main or ""
            rank = double.r_sum or 0

            players_data.append({
                'pair_id': double.id,               # ID пары
                'choice_id': None,                  # для пар не используется Choice
                'player_id': double.id,             # используем id пары как player_id
                'name': name,                       # ФИО пары (сокращённо)
                'full_name': double.para_full or f"{double.player_1} / {double.player_2}",
                'city': region,                     # регион как "город"
                'region': region,                   # регион
                'rank': rank,                       # сумма рейтинга
                'group': 1,                         # для пар одна группа
                'position': double.posev or 0,      # текущий посев
                'place': 0,
                'coach': "",                        # тренер для пар не используется
                'sex': vid,
                'player_1': double.player_1,
                'player_2': double.player_2,
            })

        # Сортировка: по рейтингу (убывание)
        players_data.sort(key=lambda x: x['rank'], reverse=True)

        import copy
        self.all_players = copy.deepcopy(players_data)

        # Устанавливаем текущего игрока (пару) и список оставшихся
        if players_data:
            self.current_player = players_data[0]
            self.players = players_data[1:]
            self.update_player_info(self.current_player)
            self.update_players_list()
            self.highlight_posev()
            self.highlight_conflicts(self.current_player)
        else:
            self.current_player = None
            self.players = []
            self.update_player_info(None)
            self.update_players_list()

    def update_players_list(self):
        """Обновляет список оставшихся игроков"""
        self.players_list.clear()
        for p in self.players:
            item = PlayerItem(p)
            self.players_list.addItem(item)
    # ----------------------------------------------
    # Отрисовка сетки
    # ----------------------------------------------
    def update_net_display(self):
        if not hasattr(self, 'net_table') or self.net_table is None:
            return

        is_pairs = self.stage_name in (
            "Мужские пары", "Женские пары", "Смешанные пары"
        )

        for pos, data in self.net_positions.items():
            row = pos - 1
            if is_pairs:
                # «Иванов И./Петров П. (Москва)»
                text = data.get('full_name') or data.get('name', '')
                if data.get('city'):
                    text = f"{text} ({data['city']})"
            else:
                text = (
                    f"{data['name']} / {data['city']} - "
                    f"{data.get('group', 1)} группа"
                )

            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignLeft)
            self.net_table.setItem(row, 1, item)

        self.highlight_conflicts(self.current_player)
        self.highlight_posev()

    def draw_net(self):
        if not self.current_system:
            return
        max_pl = self.max_players
        self.net_table.setRowCount(max_pl)
        self.net_table.setColumnCount(2)
        self.net_table.setHorizontalHeaderLabels(["№", "Игрок / Город"])
        self.net_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.net_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        # Высота строк
        if max_pl > 20:
            self.net_table.verticalHeader().setDefaultSectionSize(18)
        else:
            self.net_table.verticalHeader().setDefaultSectionSize(24)

        # Заполняем данными
        for pos in range(1, max_pl + 1):
            row = pos - 1
            item = QTableWidgetItem(str(pos))
            item.setTextAlignment(Qt.AlignCenter)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.net_table.setItem(row, 0, item)
            self.net_table.setItem(row, 1, QTableWidgetItem(""))

        # Устанавливаем делегат для отрисовки линий между четвертями
        quarter_size = max_pl // 4 if max_pl >= 8 else max_pl
        delegate = QuarterLineDelegate(self.net_table, quarter_size, max_pl)
        self.net_table.setItemDelegate(delegate)

        self.net_table.resizeColumnsToContents()
        self.net_table.resizeRowsToContents()
    # ----------------------------------------------
    # Размещение игрока
    # ----------------------------------------------
    def place_player(self, pos, player_data):
        """Размещает игрока на позиции (без удаления из списка)"""
        self.net_positions[pos] = {
            'player_id': player_data['player_id'],
            'name': player_data['name'],
            'city': player_data['city'],
            'group': player_data['group'],
            'choice_id': player_data['choice_id']
        }

    def place_current_player(self, pos):
        """Размещает текущего игрока на указанной позиции"""
        if not self.current_player:
            return False
        player_data = self.current_player
        self._place_player_on_position(pos, player_data)
        # Переходим к следующему игроку
        if self.players:
            self.current_player = self.players.pop(0)
            self.update_player_info(self.current_player)
            self.highlight_conflicts(self.current_player)
            self.get_seed_positions(pos)
            self.highlight_zones_for_current_player()  
            self.highlight_posev()
        else:
            self.current_player = None
            self.update_player_info(None)

        # self.highlight_zones_for_current_player()    
        self.update_players_list()
        self.status_label.setText(f"Игрок {player_data['name']} размещён на позиции {pos}")
        return True
    # ----------------------------------------------
    # Обработчики событий
    # ----------------------------------------------
    def on_net_cell_clicked(self, row, col):
        
        if not self.current_player:
            QMessageBox.warning(self, "Ошибка", "Нет игроков для жеребьёвки")
            return
        pos = row + 1
        if pos < 1 or pos > self.max_players:
            return

        if pos in self.net_positions:
            # Позиция занята – меняем игроков
            old_player_data = self.net_positions[pos]
            # Удаляем старого с позиции
            del self.net_positions[pos]
            # Размещаем текущего на эту позицию
            self._place_player_on_position(pos, self.current_player)
            # Старый игрок становится текущим
            self.current_player = old_player_data
            # Обновляем список
            self.update_players_list()
            # Обновляем информацию и подсветку
            self.update_player_info(old_player_data)
            self.highlight_conflicts(old_player_data)
            self.status_label.setText(f"Замена: {old_player_data['name']} на позицию {pos}")

            self.highlight_zones_for_current_player()
            return

        # Если позиция свободна
        self.place_current_player(pos)

    def on_list_item_clicked(self, item):
        if not item:
            return
        player_data = item.player_data
        # Делаем выбранного игрока текущим, а старого текущего возвращаем в список
        old_current = self.current_player
        if old_current:
            # Добавляем старого текущего в список (в начало)
            self.players.insert(0, old_current)
        self.current_player = player_data
        # Удаляем выбранного из списка
        for i, p in enumerate(self.players):
            if p['player_id'] == player_data['player_id']:
                self.players.pop(i)
                break
        self.update_player_info(self.current_player)
        self.update_players_list()
        self.update_net_display()
        self.highlight_zones_for_current_player()
    # ----------------------------------------------
    # Подсветка
    # ----------------------------------------------
    def highlight_conflicts(self, selected_player=None):
        """Подсвечивает игроков из того же региона или тренера"""
        for row in range(self.net_table.rowCount()):
            item = self.net_table.item(row, 1)
            if item:
                item.setBackground(Qt.white)

        if not selected_player:
            return

        region = selected_player.get('region', '')
        coach = selected_player.get('coach', '')

        for pos, data in self.net_positions.items():
            player = Player.get_or_none(Player.id == data['player_id'])
            if not player:
                continue
            p_region = player.region or ''
            p_coach = ''
            if player.coach_id:
                coach_obj = Coach.get_or_none(Coach.id == player.coach_id)
                if coach_obj:
                    p_coach = coach_obj.coach or ''

            if region and p_region == region:
                row = pos - 1
                item = self.net_table.item(row, 1)
                if item:
                    item.setBackground(QColor(244, 164, 96))  # светло-оранжевый
            if coach and p_coach == coach:
                row = pos - 1
                item = self.net_table.item(row, 1)
                if item:
                    item.setBackground(QColor(240, 128, 128))  # светло-красный

    def highlight_posev(self):
        """Голубая подсветка номеров посева для текущего игрока.
        Не стирает серые зоны (только белый → голубой на свободных позициях)."""
        if not hasattr(self, 'net_table') or self.net_table is None:
            return
        if not self.current_player:
            return
        if not hasattr(self, 'all_players'):
            return

        blue_bg = QColor(173, 216, 230)
        gray_bg = QColor(230, 230, 230)

        # 1) Сбрасываем ПРЕДЫДУЩИЕ голубые в белый (серые не трогаем)
        for row in range(self.net_table.rowCount()):
            item = self.net_table.item(row, 0)
            if item and item.background().color() == blue_bg:
                item.setBackground(Qt.white)

        # 2) Определяем seed-позиции текущего игрока
        try:
            idx = self.all_players.index(self.current_player)
            player_index = idx + 1
        except ValueError:
            return
        seed_positions = self.get_seed_positions(player_index)
        if not seed_positions:
            return

        # 3) Красим голубым незанятые seed-позиции; серое — перекрываем голубым,
        #    потому что seed-позиция = рекомендованная, она важнее
        for pos in seed_positions:
            if pos in self.net_positions:
                continue
            row = pos - 1
            item = self.net_table.item(row, 0)
            if item:
                item.setBackground(blue_bg)
    # ----------------------------------------------
    # Подсветка зон (половина/четверть) по правилам 2/3/4-х выходов
    # ----------------------------------------------
    def highlight_zones_for_current_player(self):
        """
        Зоны (половина/четверть) по правилам 2/3/4-х выходов.
        Голубая подсветка seed-позиций НЕ перебивается — серая кладётся
        только на не-голубые незанятые позиции.
        """
        if not hasattr(self, 'net_table') or self.net_table is None:
            return
        if not self.current_player or not self.current_system:
            return

        # 1) Сначала сбрасываем ТОЛЬКО серый на номерах (голубые не трогаем).
        gray_bg = QColor(230, 230, 230)
        for row in range(self.net_table.rowCount()):
            item = self.net_table.item(row, 0)
            if item and item.background().color() == gray_bg:
                item.setBackground(Qt.white)

        count_exit = getattr(self.current_system, 'mesta_exit', 1) or 1
        if count_exit < 2:
            return

        # 2) Определяем посев игрока относительно диапазона мест.
        my_rank = self._get_my_seed_rank(self.current_player)
        if my_rank is None or my_rank < 2:
            return  # P1 не подсвечиваем — ему и так голубым показаны позиции

        bracket = self.max_players
        half_size = bracket // 2
        quarter_size = bracket // 4

        def get_half(pos):
            return 1 if pos <= half_size else 2

        def get_quarter(pos):
            if pos <= quarter_size:       return 1
            if pos <= 2 * quarter_size:   return 2
            if pos <= 3 * quarter_size:   return 3
            return 4

        def opposite_quarter(q):
            return {1: 2, 2: 1, 3: 4, 4: 3}[q]

        def quarter_range(q):
            return range((q - 1) * quarter_size + 1, q * quarter_size + 1)

        # 3) Ищем P1/P2 своей группы среди уже размещённых
        my_group = self.current_player.get('group')
        p1_pos = None
        p2_pos = None
        for pos, np in self.net_positions.items():
            src = self._source_player_data(pos)
            if not src or src.get('group') != my_group:
                continue
            r = self._get_my_seed_rank(src)
            if r == 1:
                p1_pos = pos
            elif r == 2:
                p2_pos = pos

        target_positions = []

        if my_rank == 2:
            if p1_pos is None:
                return
            p1_half = get_half(p1_pos)
            if p1_half == 1:
                target_positions = list(range(half_size + 1, bracket + 1))
            else:
                target_positions = list(range(1, half_size + 1))

        elif my_rank == 3:
            if p2_pos is None:
                return
            p2_q = get_quarter(p2_pos)
            target_q = opposite_quarter(p2_q)
            target_positions = list(quarter_range(target_q))

        elif my_rank == 4:
            if p1_pos is None:
                return
            p1_q = get_quarter(p1_pos)
            target_q = opposite_quarter(p1_q)
            target_positions = list(quarter_range(target_q))

        else:
            return

        # 4) Красим СЕРЫМ только НЕ-голубые незанятые позиции.
        blue_bg = QColor(173, 216, 230)  # цвет seed-подсветки
        for pos in target_positions:
            if pos in self.net_positions:
                continue
            row = pos - 1
            item = self.net_table.item(row, 0)
            if item and item.background().color() != blue_bg:
                item.setBackground(gray_bg)

    def _get_my_seed_rank(self, player_data):
        """
        Определяет номер посева игрока (1, 2, 3, 4) ОТНОСИТЕЛЬНО диапазона
        мест, выходящих в этот финал.
        P1 = min(place), P2 = следующее, P3 = следующее, P4 = следующее.
        Возвращает None, если не удаётся определить.
        """
        if not player_data:
            return None
        place = player_data.get('place') or 0
        if not place:
            return None

        # получаем «nums» — те же места, что используются при загрузке
        try:
            final_info = self.parent.real_place_for_final(self.stage_name)
        except Exception:
            final_info = None
        if not final_info or 'place_stage' not in final_info:
            # fallback: считаем, что place и есть посев (1..4)
            return place if 1 <= place <= 4 else None

        nums = sorted(final_info['place_stage'])
        if place not in nums:
            return None
        # индекс в nums + 1 = относительный посев
        return nums.index(place) + 1

    def _source_player_data(self, pos):
        """Полные данные игрока, занимающего позицию pos (для определения его group/place)."""
        if pos not in self.net_positions:
            return None
        np = self.net_positions[pos]
        pid = np.get('player_id')
        # Ищем в all_players
        for p in getattr(self, 'all_players', []):
            if p.get('player_id') == pid:
                return p
        return None

    def get_seed_positions(self, player_index):
        if not hasattr(self.parent, 'setka_choice_number'):
            return []
        try:
            count_exit = self.current_system.mesta_exit or 1
            posev_structure = self.parent.setka_choice_number(self.stage_name, count_exit)
            if not posev_structure:
                return []
            total_players = posev_structure[0]
            if player_index > total_players:
                return []
            groups = []
            start_idx = 1
            for level in posev_structure[1:]:
                for group in level:
                    end_idx = start_idx + len(group) - 1
                    groups.append({
                        'start': start_idx,
                        'end': end_idx,
                        'positions': group
                    })
                    start_idx = end_idx + 1
            for g in groups:
                if g['start'] <= player_index <= g['end']:
                    return g['positions']
            return []
        except Exception as e:
            print(f"Ошибка получения позиций посева: {e}")
            return []
    # ----------------------------------------------
    # Информация об игроке
    # ----------------------------------------------
    def update_player_info(self, player_data):
        """Обновляет информацию о текущем игроке (или паре)"""
        if not player_data:
            self.player_info['name'].setText("-")
            self.player_info['city'].setText("-")
            self.player_info['region'].setText("-")
            self.player_info['coach'].setText("-")
            self.player_info['group'].setText("-")
            return

        # Проверяем, является ли это парой
        if 'player_1' in player_data and 'player_2' in player_data:
            # Для пар
            name = f"{player_data.get('player_1', '')} / {player_data.get('player_2', '')}"
            self.player_info['name'].setText(name)
            self.player_info['city'].setText(player_data.get('city', "-"))
            self.player_info['region'].setText(player_data.get('region', "-"))
            self.player_info['coach'].setText(f"Рейтинг: {player_data.get('rank', 0)}")
        else:
            # Для личных соревнований (старая логика)
            self.player_info['name'].setText(player_data.get('name', "-"))
            self.player_info['city'].setText(player_data.get('city', "-"))
            self.player_info['region'].setText(player_data.get('region', "-"))
            self.player_info['coach'].setText(player_data.get('coach', "-"))
            group_num = f"{player_data['group']} группа"
            self.player_info['group'].setText(group_num)

        # ---- подсветка зон посева ----     
        self.highlight_zones_for_current_player()
        self.highlight_posev()
    # ----------------------------------------------
    # Загрузка существующей жеребьёвки
    # ----------------------------------------------
    def load_existing_net(self):
        """Загрузка существующей сетки из Game_list (личные и пары)."""
        if not self.current_system:
            return

        game_players = Game_list.select().where(
            (Game_list.title_id == self.title_id) &
            (Game_list.system_id == self.current_system.id)
        ).order_by(Game_list.rank_num_player)

        is_pairs = self.stage_name in (
            "Мужские пары", "Женские пары", "Смешанные пары"
        )

        self.net_positions = {}

        for gp in game_players:
            pos = gp.rank_num_player

            if is_pairs:
                # ─── ПАРЫ ───
                if not gp.player_double_id:
                    # на всякий случай пропускаем — такого не должно быть
                    continue
                pair_id = gp.player_double_id.id
                pair = Players_double.get_or_none(Players_double.id == pair_id)
                if not pair:
                    continue

                name_short = pair.para_shot or f"{pair.player_1} / {pair.player_2}"
                name_full = pair.para_full or name_short
                city = pair.region_main or ""

                self.net_positions[pos] = {
                    'player_id': pair_id,
                    'name': name_short,
                    'city': city,
                    'group': 1,          # для пар всегда «1 группа» — не используется
                    'full_name': name_full,
                    'player_1': pair.player_1,
                    'player_2': pair.player_2,
                }
                # Удаляем пару из списка ожидания (если там есть)
                for i, p in enumerate(self.players):
                    if p.get('player_id') == pair_id:
                        self.players.pop(i)
                        break

            else:
                # ─── ЛИЧНЫЕ ───
                if not gp.player_group:
                    continue
                player = Player.get_or_none(Player.id == gp.player_group.id)
                if not player:
                    continue

                self.net_positions[pos] = {
                    'player_id': player.id,
                    'name': player.fio or player.player,
                    'city': player.city or "",
                    'group': getattr(player, 'group', None) or 1,
                }
                for i, p in enumerate(self.players):
                    if p.get('player_id') == player.id:
                        self.players.pop(i)
                        break

        self.update_net_display()
    # ----------------------------------------------
    # Сохранение
    # ----------------------------------------------
    def save_drawing(self):
        paries_list = ["Мужские пары", "Женские пары", "Смешанные пары"]

        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Сохранить жеребьёвку для {self.stage_name}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        
        try:
            if self.stage_name in paries_list:
                Choice_double_player.update(posev=0).where(
                    (Choice_double_player.title_id == self.title_id) &
                    (Choice_double_player.vid_para == self.sex)
                ).execute()
            else:
                Choice.update(posev_final=0, final="").where(
                    (Choice.title_id == self.title_id) &
                    (Choice.sex == self.sex) &
                    (Choice.final == self.stage_name)
                ).execute()

            Game_list.delete().where(
                (Game_list.title_id == self.title_id) &
                (Game_list.system_id == self.current_system.id)
            ).execute()
            
            Result.delete().where(
                (Result.title_id == self.title_id) &
                (Result.system_id == self.current_system.id)
            ).execute()

            if self.stage_name in paries_list:
                for pos, data in self.net_positions.items():
                    Choice_double_player.update(posev=pos).where(
                        (Choice_double_player.title_id == self.title_id) &
                        (Choice_double_player.vid_para == self.sex) & 
                        (Choice_double_player.player_double_id == data['player_id'])
                    ).execute()

                choices = Choice_double_player.select().where((Choice_double_player.title_id == self.title_id) &
                                                (Choice_double_player.vid_para == self.sex)
                                                )
            else:
                for pos, data in self.net_positions.items():
                    Choice.update(posev_final=pos, final=self.stage_name).where(
                        (Choice.title_id == self.title_id) &
                        (Choice.sex == self.sex) & 
                        (Choice.player_choice_id == data['player_id'])
                    ).execute()

                choices = Choice.select().where((Choice.title_id == self.title_id) &
                                                (Choice.final == self.stage_name) &
                                                (Choice.sex == self.sex)
                                                )
            # ===== если не полная сетка записываем Х на свободные места
            self.free_place_in_setka()

            posev_data = {} # окончательные посев номер в сетке - игрок/ город

            for i in self.net_positions.keys():
                id = self.net_positions[i]['player_id']
                name_x = self.net_positions[i]['name']
                if name_x == "X":
                    # Получаем ID игрока X
                    # x_player_id = self.get_x_player_id()
                    x_player_id = id
                    posev_data[i] = {
                    'player_id':x_player_id,
                        'name_city':'X',
                        'name':'X'
                    }
                else:
                    if self.stage_name in paries_list:
                        pl_id = Players_double.get(Players_double.id == id)
                        family_city = pl_id.para_full
                        family_shot = pl_id.para_shot
                        posev_data[i] = {
                        'player_id':id,
                            'name_city':family_city,
                            'name':family_shot
                        }
                    else:
                        pl_id = Player.get(Player.id == id)
                        family_city = pl_id.fio_city
                        family_shot = pl_id.fio
                        posev_data[i] = {
                        'player_id':id,
                            'name_city':family_city,
                            'name':family_shot
                        }
            # # заполняем Game_list Choice
           
            for pos, data in self.net_positions.items():
                if self.stage_name in paries_list:
                    Game_list.create(
                        number_group=self.stage_name,
                        rank_num_player=pos,
                        player_double_id=data['player_id'],
                        system_id=self.current_system.id,
                        title_id=self.title_id,
                        sex=self.sex if self.sex else "man"
                    )
                else:
                    Game_list.create(
                        number_group=self.stage_name,
                        rank_num_player=pos,
                        player_group_id=data['player_id'],
                        system_id=self.current_system.id,
                        title_id=self.title_id,
                        sex=self.sex if self.sex else "man"
                    )

            # # 7. Создаём туры и матчи заполняем Results
            max_pl = self.max_players
            # число игр в сетке
            total_game = self.parent.number_game_of_net(self.stage_name)
            # =========== проба записи стадии ====
            # наивысшее место 
            highest_place = self.parent.get_final_start_place(self.stage_name)
            # # определяет количество игр в сетке
            game = self.parent.number_game_of_net(self.stage_name)

            self.parent.get_match_title(i, game, highest_place, max_pl)
            # =======================
            # присваивает встречи 1-ого тура и записывает в тбл Results
            for i in range(1, max_pl // 2 + 1):   
                pl1 = posev_data[i * 2 - 1]['name_city']
                pl2 = posev_data[i * 2]['name_city']
                if pl1 is not None and pl2 is not None:
                    with db:
                        results = Result(number_group=self.stage_name, system_stage='финальный', player1=pl1, player2=pl2,
                                        tours=i, title_id=self.title_id,
                                        system_id=self.current_system.id, sex=self.sex).save()
            # дополняет номера будущих встреч            
            for i in range(max_pl // 2 + 1, total_game + 1): 
                with db:
                    results = Result(number_group=self.stage_name, system_stage="финальный", player1="", player2="",
                                    tours=i, title_id=self.title_id,
                                    system_id=self.current_system.id, sex=self.sex).save()

            # записывает стадии сетки в Result
            stadia = self.parent.whrite_stadia_on_net(game, highest_place, max_pl)

            results_stadia = Result.select().where(
                (Result.title_id == self.title_id) &
                (Result.system_id == self.current_system.id))

            for k in results_stadia:
                num_game = int(k.tours)
                stadia_str = stadia[num_game]
                Result.update(stage_net=stadia_str).where(Result.id == k).execute()

            System.update(choice_flag=1).where(System.id == self.current_system.id).execute()

            QMessageBox.information(self, "Успех", f"Жеребьёвка для {self.stage_name} сохранена")
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить жеребьёвку: {str(e)}")
    # ----------------------------------------------
    # Закрытие окна
    # ----------------------------------------------
    def closeEvent(self, event):
        if self.net_positions:
            reply = QMessageBox.question(
                self,
                "Сохранение жеребьёвки",
                "Вы хотите сохранить текущую жеребьёвку?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Cancel:
                event.ignore()
                return
            elif reply == QMessageBox.Yes:
                self.save_drawing()
                event.accept()
            else:
                event.accept()
        else:
            event.accept()
    # ----------------------------------------------
    # свободные номера в сетке
    # ----------------------------------------------
    def free_place_in_setka(self):
        """находит свободные места в сетке"""
        free_num = []
        for row in range(0, self.max_players):
            item = self.net_table.item(row, 1).text()
            if item == "":
                value = self.net_table.item(row, 0).text()
                free_num.append(int(value))

        # # Получаем ID игрока X
        # x_player_id = self.parent.get_x_player_id()

        # # Создаем данные для игрока X
        # x_player_data = {
        #     'player_id': x_player_id,  # id
        #     'name': "X",          # name
        #     'region': "",           # region
        #     'group_number': 0,            # group_number
        #     'group': "",           # group
        #     'city': "",           # city
        #     'rank': 0,            # rank
        #     'place': 0             # place
        # }

        is_pairs = self.stage_name in (
            "Мужские пары", "Женские пары", "Смешанные пары"
        )

        if is_pairs:
            x_player_id = self.parent.get_or_create_x_double(self.sex)
        else:
            x_player_id = self.parent.get_x_player_id()

        if not x_player_id:
            # не смогли получить/создать X — прерываем
            QMessageBox.warning(
                self, "Ошибка",
                f"Не удалось получить игрока X для {'пар' if is_pairs else 'личных'}."
            )
            return

        x_player_data = {
            'player_id': x_player_id,
            'name': "X",
            'region': "",
            'group_number': 0,
            'group': "",
            'city': "",
            'rank': 0,
            'place': 0,
        }

        # Заполняем свободные места данными игрока X
        for pos in free_num:
            self.net_positions[pos] = x_player_data

    def fill_empty_positions_with_x(self):
            """Заполняет свободные позиции игроком X"""
            x_player_id = self.parent.get_x_player_id() if hasattr(self.parent, 'get_x_player_id') else None
            if not x_player_id:
                QMessageBox.warning(self, "Ошибка", "Не удалось получить ID игрока X")
                return

            # Находим свободные позиции
            free_positions = [pos for pos in range(1, self.max_players + 1) if pos not in self.net_positions]
            for pos in free_positions:
                self.net_positions[pos] = {
                    'player_id': x_player_id,
                    'name': 'X',
                    'city': '',
                    'choice_id': None,
                    'group': ''
                }
            self.update_net_display()

    def create_results_for_pairs(self):
        """Создаёт записи в таблице Result для парного этапа согласно сетке"""
        if not self.current_system:
            return

        # Определяем этап
        stage_name = self.stage_name
        system = self.current_system
        max_player = system.max_player  # количество пар в сетке
        type_table = system.type_table

        # Удаляем старые записи Result для этого этапа
        Result.delete().where(
            (Result.title_id == self.title_id) &
            (Result.system_id == system.id)
        ).execute()

        # Получаем все пары в порядке посева из Game_list
        game_pairs = Game_list.select().where(
            (Game_list.title_id == self.title_id) &
            (Game_list.system_id == system.id)
        ).order_by(Game_list.rank_num_player)

        # Словарь: позиция -> данные пары
        pair_by_pos = {}
        for gp in game_pairs:
            pair_id = gp.player_double_id.id if gp.player_double_id else None
            if not pair_id:
                continue
            double = Players_double.get_or_none(Players_double.id == pair_id)
            if not double:
                continue
            pair_name = double.para_full or f"{double.player_1} / {double.player_2}"
            pair_by_pos[gp.rank_num_player] = pair_name

        # Создаём матчи первого раунда (пары 1-2, 3-4, ...)
        total_games = self.parent.number_game_of_net(stage_name) if hasattr(self.parent, 'number_game_of_net') else max_player * 2

        first_round_count = max_player // 2
        for i in range(1, first_round_count + 1):
            pos1 = i * 2 - 1
            pos2 = i * 2
            p1 = pair_by_pos.get(pos1, "")
            p2 = pair_by_pos.get(pos2, "")

            if p1 and p2:
                Result.create(
                    number_group=stage_name,
                    system_stage=stage_name,
                    tours=str(i),
                    player1=p1,
                    player2=p2,
                    title_id=self.title_id,
                    system_id=system.id,
                    round=1,
                    sex=self.sex if self.sex else "man"
                )

        # Создаём пустые записи для последующих раундов
        for game_num in range(first_round_count + 1, total_games + 1):
            Result.create(
                number_group=stage_name,
                system_stage=stage_name,
                tours=str(game_num),
                player1="",
                player2="",
                title_id=self.title_id,
                system_id=system.id,
                round=1,
                sex=self.sex if self.sex else "man"
            )

        print(f"Создано {total_games} записей в Result для {stage_name}")      
# ======new =====
    def _place_player_on_position(self, pos, player_data):
        """Размещает игрока на позиции, удаляя его из списка оставшихся"""
        # Добавляем в сетку
        self.net_positions[pos] = {
            'player_id': player_data['player_id'],
            'name': player_data['name'],
            'city': player_data['city'],
            'choice_id': player_data['choice_id'],
            'group': player_data['group']
        }
        # Удаляем из списка оставшихся
        for i in range(self.players_list.count()):
            item = self.players_list.item(i)
            if item.player_data['player_id'] == player_data['player_id']:
                self.players_list.takeItem(i)
                break
        # Удаляем из self.players, если он там ещё есть
        self.players = [p for p in self.players if p['player_id'] != player_data['player_id']]
        self.update_net_display()

    def update_players_list(self):
        self.players_list.clear()
        for p in self.players:
            item = PlayerItem(p)
            self.players_list.addItem(item)
 
class QuarterLineDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, quarter_size=0, max_players=0):
        super().__init__(parent)
        self.quarter_size = quarter_size
        self.max_players = max_players

    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        if self.quarter_size == 0 or self.max_players == 0:
            return

        row = index.row()
        # Проверяем, является ли строка последней в четверти
        # и не последняя ли это четверть в таблице
        if (row + 1) % self.quarter_size == 0 and row + 1 < self.max_players:
            painter.save()
            pen = QPen(QColor(210, 180, 140), 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawLine(option.rect.left(), option.rect.bottom(),
                             option.rect.right(), option.rect.bottom())
            painter.restore()