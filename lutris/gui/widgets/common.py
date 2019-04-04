"""Misc widgets used in the GUI."""
import os

from gi.repository import Gtk, GObject, Pango

from lutris.util.log import logger
from lutris.util import system


class SlugEntry(Gtk.Entry, Gtk.Editable):
    def __init__(self):
        super(SlugEntry, self).__init__()

    def do_insert_text(self, new_text, length, position):
        """Filter inserted characters to only accept alphanumeric and dashes"""
        new_text = "".join([c for c in new_text if c.isalnum() or c == "-"]).lower()
        length = len(new_text)
        self.get_buffer().insert_text(position, new_text, length)
        return position + length


class NumberEntry(Gtk.Entry, Gtk.Editable):
    def __init__(self):
        super(NumberEntry, self).__init__()

    def do_insert_text(self, new_text, length, position):
        """Filter inserted characters to only accept numbers"""
        new_text = "".join([c for c in new_text if c.isnumeric()])
        if new_text:
            self.get_buffer().insert_text(position, new_text, length)
            return position + length
        return position


class FileChooserEntry(Gtk.Box):
    """Editable entry with a file picker button"""

    max_completion_items = 15  # Maximum number of items to display in the autocompletion dropdown.

    def __init__(
            self,
            title="Select file",
            action=Gtk.FileChooserAction.OPEN,
            path=None,
            default_path=None
    ):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            visible=True
        )
        self.title = title
        self.action = action
        self.path = os.path.expanduser(path) if path else None
        self.default_path = os.path.expanduser(default_path) if default_path else path

        self.path_completion = Gtk.ListStore(str)

        self.entry = Gtk.Entry(visible=True)
        self.entry.set_completion(self.get_completion())
        self.entry.connect("changed", self.on_entry_changed)
        if path:
            self.entry.set_text(path)

        browse_button = Gtk.Button("Browse...", visible=True)
        browse_button.connect("clicked", self.on_browse_clicked)

        box = Gtk.Box(spacing=6, visible=True)
        box.pack_start(self.entry, True, True, 0)
        box.add(browse_button)
        self.add(box)

    def get_text(self):
        """Return the entry's text"""
        return self.entry.get_text()

    def get_filename(self):
        """Deprecated"""
        logger.warning("Just use get_text")
        return self.get_text()

    def get_completion(self):
        """Return an EntryCompletion widget"""
        completion = Gtk.EntryCompletion()
        completion.set_model(self.path_completion)
        completion.set_text_column(0)
        return completion

    def get_filechooser_dialog(self):
        """Return an instance of a FileChooserDialog configured for this widget"""
        dialog = Gtk.FileChooserDialog(
            title=self.title, transient_for=None, action=self.action
        )
        dialog.add_buttons(
            "_Cancel", Gtk.ResponseType.CLOSE,
            "_OK", Gtk.ResponseType.OK
        )
        dialog.set_create_folders(True)
        dialog.set_current_folder(self.get_default_folder())
        dialog.connect("response", self.on_select_file)
        return dialog

    def get_default_folder(self):
        """Return the default folder for the file picker"""
        default_path = self.path or self.default_path or ""
        if not default_path or not system.path_exists(default_path):
            current_entry = self.get_text()
            if system.path_exists(current_entry):
                default_path = current_entry
        if not os.path.isdir(default_path):
            default_path = os.path.dirname(default_path)
        return os.path.expanduser(default_path or "~")

    def on_browse_clicked(self, _widget):
        """Browse button click callback"""
        file_chooser_dialog = self.get_filechooser_dialog()
        file_chooser_dialog.run()

    def on_entry_changed(self, widget):
        """Entry changed callback"""
        self.update_completion(widget.get_text() or "/")
        self.clear_warnings()

    def on_select_file(self, dialog, response):
        """FileChooserDialog response callback"""
        if response == Gtk.ResponseType.OK:
            target_path = dialog.get_filename()
            if target_path:
                dialog.set_current_folder(target_path)
                self.entry.set_text(system.reverse_expanduser(target_path))
        dialog.hide()

    def update_completion(self, current_path):
        """Update the auto-completion widget with the current path"""
        self.path_completion.clear()

        if not os.path.exists(current_path):
            current_path, filefilter = os.path.split(current_path)
        else:
            filefilter = None

        if os.path.isdir(current_path):
            index = 0
            for filename in sorted(os.listdir(current_path)):
                if filename.startswith("."):
                    continue
                if filefilter is not None and not filename.startswith(filefilter):
                    continue
                self.path_completion.append([os.path.join(current_path, filename)])
                index += 1
                if index > self.max_completion_items:
                    break

    def clear_warnings(self):
        """Delete all the warning labels from the container"""
        for child in self.get_children():
            if isinstance(child, Gtk.Label):
                child.destroy()


class Label(Gtk.Label):
    """Standardised label for config vboxes."""

    def __init__(self, message=None):
        """Custom init of label."""
        super().__init__(label=message)
        self.set_line_wrap(True)
        self.set_max_width_chars(22)
        self.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.set_size_request(230, -1)
        self.set_alignment(0, 0.5)
        self.set_justify(Gtk.Justification.LEFT)


class VBox(Gtk.Box):
    def __init__(self, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, margin_top=18, **kwargs)


class EditableGrid(Gtk.Grid):
    __gsignals__ = {"changed": (GObject.SIGNAL_RUN_FIRST, None, ())}

    def __init__(self, data, columns):
        self.columns = columns
        super().__init__()
        self.set_column_homogeneous(True)
        self.set_row_homogeneous(True)
        self.set_row_spacing(10)
        self.set_column_spacing(10)

        self.liststore = Gtk.ListStore(str, str)
        for item in data:
            self.liststore.append([str(value) for value in item])

        self.treeview = Gtk.TreeView.new_with_model(self.liststore)
        self.treeview.set_grid_lines(Gtk.TreeViewGridLines.BOTH)
        for i, column_title in enumerate(self.columns):
            renderer = Gtk.CellRendererText()
            renderer.set_property("editable", True)
            renderer.connect("edited", self.on_text_edited, i)

            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            column.set_resizable(True)
            column.set_min_width(100)
            column.set_sort_column_id(0)
            self.treeview.append_column(column)

        self.buttons = []
        self.add_button = Gtk.Button("Add")
        self.buttons.append(self.add_button)
        self.add_button.connect("clicked", self.on_add)

        self.delete_button = Gtk.Button("Delete")
        self.buttons.append(self.delete_button)
        self.delete_button.connect("clicked", self.on_delete)

        self.scrollable_treelist = Gtk.ScrolledWindow()
        self.scrollable_treelist.set_vexpand(True)
        self.scrollable_treelist.add(self.treeview)

        self.attach(self.scrollable_treelist, 0, 0, 5, 5)
        self.attach(self.add_button, 5 - len(self.buttons), 6, 1, 1)
        for i, button in enumerate(self.buttons[1:]):
            self.attach_next_to(button, self.buttons[i], Gtk.PositionType.RIGHT, 1, 1)
        self.show_all()

    def on_add(self, widget):
        self.liststore.append(["", ""])
        self.emit("changed")

    def on_delete(self, widget):
        selection = self.treeview.get_selection()
        liststore, iter = selection.get_selected()
        self.liststore.remove(iter)
        self.emit("changed")

    def on_text_edited(self, widget, path, text, field):
        self.liststore[path][field] = text
        self.emit("changed")

    def get_data(self):
        model_data = []
        for row in self.liststore:
            model_data.append([col for col in row])
        return model_data
