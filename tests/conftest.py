# The opt-in pattern every tool repo uses; core dogfoods it so the plugin's
# fixture registration path is exercised by its own suite.
pytest_plugins = ("mythings.testing",)
