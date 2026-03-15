from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import DataTable, Input, Label, Markdown, Static


class NodeList(DataTable):
    """
    显示图谱节点的列表组件。
    """

    class Selected(Message):
        def __init__(self, node_id: str):
            self.node_id = node_id
            super().__init__()

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.add_columns("ID", "Type", "Name")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        # Get the first cell (ID) of the selected row
        node_id = self.get_row_at(event.cursor_row)[0]
        self.post_message(self.Selected(node_id))


class NodeDetail(Markdown):
    """
    显示选中节点详情的 Markdown 组件。
    """

    pass


class ConfigPanel(Vertical):
    """
    配置面板（只读）。
    """

    def compose(self) -> ComposeResult:
        yield Label("Semantic Threshold:")
        yield Input(placeholder="0.85", value="0.85", id="threshold_input")
        yield Static(id="status_area", content="Read-only mode")
