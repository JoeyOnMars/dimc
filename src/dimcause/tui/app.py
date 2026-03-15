import logging

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Footer, Header

from dimcause.core.event_index import EventIndex
from dimcause.storage.graph_store import GraphStore
from dimcause.tui.widgets import ConfigPanel, NodeDetail, NodeList

# Setup logging to file to avoid messing up TUI
logging.basicConfig(filename="dimcause_tui.log", level=logging.INFO)


class GraphExploreApp(App):
    """
    Dimcause Graph Explorer TUI Application.
    """

    TITLE = "Dimcause Graph Explorer"
    CSS = """
    Screen {
        layout: horizontal;
    }

    #sidebar {
        width: 30%;
        height: 100%;
        dock: left;
        border-right: solid green;
    }

    #main_content {
        width: 70%;
        height: 100%;
        padding: 1;
    }

    NodeList {
        height: 70%;
    }

    ConfigPanel {
        height: 30%;
        border-top: solid blue;
        padding: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh_list", "Refresh"),
    ]

    def __init__(self):
        super().__init__()
        self.store = GraphStore()
        self.index = EventIndex()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Vertical(NodeList(id="node_list"), ConfigPanel(id="config_panel"), id="sidebar"),
            Container(NodeDetail(id="node_detail"), id="main_content"),
        )
        yield Footer()

    def on_mount(self) -> None:
        self.action_refresh_list()

    def action_refresh_list(self) -> None:
        table = self.query_one(NodeList)
        table.clear()

        # Load nodes from GraphStore (via SQLite)
        # We'll list all nodes for now. In real app, might want pagination.
        # But SQLite query is fast.
        conn = self.store._get_conn()
        try:
            cursor = conn.execute("SELECT id, type, data FROM graph_nodes LIMIT 1000")
            for row in cursor:
                # row: (id, type, data_json_str)
                # We can try to extract a name/summary from data if possible
                node_id, node_type, _ = row
                table.add_row(node_id, node_type, node_id)  # Using ID as name for now
        finally:
            conn.close()

    def on_node_list_selected(self, message: NodeList.Selected) -> None:
        """Handle node selection"""
        node_id = message.node_id

        # Determine if it's an event or file
        # We can try loading from EventIndex first
        event = self.index.load_event(node_id)

        if event:
            # Render event markdown
            content = f"# {event.id}\n\n**Type**: {event.type}\n\n"
            content += event.content

            # Show links if available (re-query graph store for edges)
            neighbors = self.store.get_neighbors(node_id)
            if neighbors:
                content += "\n\n## Causal Links\n"
                for edge in neighbors:
                    content += f"- **{edge.relation}** -> {edge.target}\n"

            self.query_one(NodeDetail).update(content)
        else:
            self.query_one(NodeDetail).update(
                f"# {node_id}\n\nNode details not found in EventIndex."
            )


if __name__ == "__main__":
    app = GraphExploreApp()
    app.run()
