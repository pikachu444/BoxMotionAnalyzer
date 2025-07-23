import tkinter as tk
from tkinter import ttk

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Box Motion Analyzer")
        self.geometry("800x600")

        self._create_menubar()
        self._create_widgets()
        self._create_statusbar()

    def _create_menubar(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Load CSV...", command=self.load_csv)
        file_menu.add_command(label="Set Output Directory...", command=self.set_output_dir)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=file_menu)

    def _create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Placeholder for other widgets
        label = ttk.Label(main_frame, text="GUI for Box Motion Analysis Pipeline")
        label.pack()


    def _create_statusbar(self):
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        statusbar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        statusbar.pack(side=tk.BOTTOM, fill=tk.X)

    def load_csv(self):
        # This will be implemented later
        self.status_var.set("Load CSV button clicked.")
        print("Load CSV button clicked.")

    def set_output_dir(self):
        # This will be implemented later
        self.status_var.set("Set Output Directory button clicked.")
        print("Set Output Directory button clicked.")


if __name__ == "__main__":
    app = Application()
    app.mainloop()
