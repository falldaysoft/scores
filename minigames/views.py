from django.views.generic import TemplateView


class PlayPageView(TemplateView):
    """Main /play page showing all three mini-games"""
    template_name = 'minigames/play.html'


class ReactionGameView(TemplateView):
    """Standalone page for Reaction Timer game"""
    template_name = 'minigames/reaction.html'


class MemoryGameView(TemplateView):
    """Standalone page for Memory Sequence game"""
    template_name = 'minigames/memory.html'


class TargetGameView(TemplateView):
    """Standalone page for Target Shooting game"""
    template_name = 'minigames/target.html'


class WhackGameView(TemplateView):
    """Standalone page for Whack-a-Mole game"""
    template_name = 'minigames/whack.html'


class SnowflakeGameView(TemplateView):
    """Standalone page for Snowflake Catcher game"""
    template_name = 'minigames/snowflakes.html'


class RiddleGameView(TemplateView):
    """Standalone page for Riddle game (correct_answer type)"""
    template_name = 'minigames/riddle.html'


class AsteroidsGameView(TemplateView):
    """Standalone page for Asteroids game"""
    template_name = 'minigames/asteroids.html'


class TileGameView(TemplateView):
    """Standalone page for Tile Puzzle game"""
    template_name = 'minigames/tiles.html'


class MinesweepGameView(TemplateView):
    """Standalone page for Minesweeper game"""
    template_name = 'minigames/minesweep.html'
