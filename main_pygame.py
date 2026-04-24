"""Alias entry point for the primary pygame-ce frontend."""

from ui.pygame_app import PygameApp


def main():
    app = PygameApp()
    app.run()


if __name__ == "__main__":
    main()
