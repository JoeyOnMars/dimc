import pytest

from dimcause.tui.app import GraphExploreApp
from dimcause.tui.widgets import ConfigPanel, NodeList


@pytest.mark.asyncio
async def test_app_instantiation():
    app = GraphExploreApp()
    assert app is not None
    assert app.title == "Dimcause Graph Explorer"


@pytest.mark.asyncio
async def test_node_list_columns():
    app = GraphExploreApp()
    async with app.run_test():
        node_list = app.query_one(NodeList)
        cols = list(node_list.columns.values())
        assert len(cols) == 3
        assert "ID" in str(cols[0].label)
        assert "Type" in str(cols[1].label)


@pytest.mark.asyncio
async def test_config_panel_input():
    app = GraphExploreApp()
    async with app.run_test():
        panel = app.query_one(ConfigPanel)
        input_widget = panel.query_one("#threshold_input")
        assert input_widget.value == "0.85"
