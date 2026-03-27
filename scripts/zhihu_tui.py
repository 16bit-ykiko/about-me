from dataclasses import dataclass


@dataclass(frozen=True)
class MenuAction:
    key: str
    label: str
    description: str


def run_menu(
    title: str, subtitle: str, actions: list[MenuAction], browse_only: bool = False
) -> str | None:
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal
    from textual.widgets import Footer, Header, OptionList, Static

    class MenuApp(App[str]):
        CSS = """
        Screen {
            background: #0b1020;
            color: #f8fafc;
        }

        Header {
            background: #16213e;
            color: #f8fafc;
        }

        Footer {
            background: #16213e;
            color: #cbd5e1;
        }

        #shell {
            height: 1fr;
            layout: horizontal;
            padding: 1 2;
        }

        #actions {
            width: 1fr;
            border: heavy #3b82f6;
            background: #111827;
        }

        #details {
            width: 40%;
            min-width: 36;
            margin-left: 2;
            border: heavy #f59e0b;
            background: #1f2937;
            padding: 1 2;
        }
        """

        BINDINGS = [
            ("q", "quit", "Quit"),
            ("escape", "quit", "Quit"),
            ("enter", "select_action", "Select" if not browse_only else "Back"),
        ]

        def __init__(self) -> None:
            super().__init__()
            self._actions = actions

        def compose(self) -> ComposeResult:
            yield Header(name=title)
            with Horizontal(id="shell"):
                yield OptionList(
                    *[action.label for action in self._actions], id="actions"
                )
                yield Static("", id="details")
            yield Footer()

        def on_mount(self) -> None:
            self.sub_title = subtitle
            self._update_details(0)

        def _update_details(self, index: int) -> None:
            if not self._actions:
                return
            action = self._actions[index]
            details = self.query_one("#details", Static)
            footer = (
                "[dim]Use arrow keys or j/k to browse. q to go back.[/dim]"
                if browse_only
                else "[dim]Use arrow keys or j/k to navigate. Enter to select. q to quit.[/dim]"
            )
            details.update(f"[b]{action.label}[/b]\n\n{action.description}\n\n{footer}")

        def on_option_list_option_highlighted(
            self, event: OptionList.OptionHighlighted
        ) -> None:
            self._update_details(event.option_index)

        def on_option_list_option_selected(
            self, event: OptionList.OptionSelected
        ) -> None:
            if browse_only:
                self.exit(None)
                return
            self.exit(self._actions[event.option_index].key)

        def action_select_action(self) -> None:
            if browse_only:
                self.exit(None)
                return
            option_list = self.query_one("#actions", OptionList)
            if option_list.highlighted is not None:
                self.exit(self._actions[option_list.highlighted].key)

    return MenuApp().run()


def run_text_input(
    title: str,
    subtitle: str,
    prompt: str,
    *,
    value: str = "",
    placeholder: str = "",
) -> str | None:
    from textual.app import App, ComposeResult
    from textual.containers import Vertical
    from textual.widgets import Footer, Header, Input, Static

    class InputApp(App[str]):
        CSS = """
        Screen {
            background: #0b1020;
            color: #f8fafc;
        }

        Header {
            background: #16213e;
            color: #f8fafc;
        }

        Footer {
            background: #16213e;
            color: #cbd5e1;
        }

        #shell {
            width: 1fr;
            height: 1fr;
            align: center middle;
        }

        #card {
            width: 80;
            max-width: 90%;
            border: heavy #3b82f6;
            background: #111827;
            padding: 1 2;
        }

        #prompt {
            margin-bottom: 1;
        }

        #input {
            margin-top: 1;
        }

        #hint {
            margin-top: 1;
            color: #94a3b8;
        }
        """

        BINDINGS = [
            ("q", "cancel", "Cancel"),
            ("escape", "cancel", "Cancel"),
            ("enter", "submit", "Submit"),
        ]

        def compose(self) -> ComposeResult:
            yield Header(name=title)
            with Vertical(id="shell"):
                with Vertical(id="card"):
                    yield Static(prompt, id="prompt")
                    yield Input(value=value, placeholder=placeholder, id="input")
                    yield Static("Enter to submit. Esc or q to cancel.", id="hint")
            yield Footer()

        def on_mount(self) -> None:
            self.sub_title = subtitle
            self.query_one("#input", Input).focus()

        def action_cancel(self) -> None:
            self.exit(None)

        def action_submit(self) -> None:
            text = self.query_one("#input", Input).value.strip()
            self.exit(text or None)

        def on_input_submitted(self, event: Input.Submitted) -> None:
            self.exit(event.value.strip() or None)

    return InputApp().run()
