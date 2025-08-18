"""
Entry point for Pathfinder Game Apprentice.
No logic here; just bootstraps the application.
"""

from society_scribe.society_scribe import SocietyScribe


def main():
    # Instantiate GameApprentice (starts Discord bot)
    society_scribe = SocietyScribe()
    society_scribe.run()


if __name__ == "__main__":
    main()
