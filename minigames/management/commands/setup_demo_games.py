from django.core.management.base import BaseCommand
from accounts.models import User
from games.models import Game
from leaderboards.models import Leaderboard


# Fixed API tokens for demo games - these are intentionally public
# so the mini-games can submit scores from client-side JavaScript
DEMO_API_TOKENS = {
    'reaction-timer': 'demo_reaction_timer_public_token_v1',
    'memory-sequence': 'demo_memory_sequence_public_token_v1',
    'target-shooting': 'demo_target_shooting_public_token_v1',
    'whack-a-mole': 'demo_whack_a_mole_public_token_v1',
    'snowflakes': 'demo_snowflakes_public_token_v1',
    'daily-riddle': 'demo_daily_riddle_public_token_v1',
    'asteroids': 'demo_asteroids_public_token_v1',
}


class Command(BaseCommand):
    help = 'Set up demo games and system user for mini-games feature'

    SYSTEM_EMAIL = 'system@scores.local'
    GAME_NAME = 'Mini Games'
    GAME_SLUG = 'mini-games'

    LEADERBOARDS = [
        {
            'name': 'Reaction Timer',
            'slug': 'reaction-timer',
            'description': 'Test your reflexes! Click as fast as you can when the screen changes color.',
            'sort_order': 'asc',  # Lower time = better
        },
        {
            'name': 'Memory Sequence',
            'slug': 'memory-sequence',
            'description': 'Remember and repeat the color sequence. How far can you go?',
            'sort_order': 'desc',  # Higher level = better
        },
        {
            'name': 'Target Shooting',
            'slug': 'target-shooting',
            'description': 'Click targets as fast as you can in 10 seconds. Smaller targets = more points!',
            'sort_order': 'desc',  # Higher score = better
        },
        {
            'name': 'Whack-a-Mole',
            'slug': 'whack-a-mole',
            'description': 'Whack moles as they pop up! Faster hits = more points.',
            'sort_order': 'desc',  # Higher score = better
        },
        {
            'name': 'Snowflake Catcher',
            'slug': 'snowflakes',
            'description': 'Catch falling snowflakes before they hit the ground! Smaller = more points.',
            'sort_order': 'desc',  # Higher score = better
        },
        {
            'name': 'Daily Riddle',
            'slug': 'daily-riddle',
            'description': 'Solve the riddle to join the leaderboard!',
            'sort_order': 'newest',  # Show most recent solvers first
            'leaderboard_type': 'correct_answer',
            'correct_answer': 'map',
        },
        {
            'name': 'Asteroids',
            'slug': 'asteroids',
            'description': 'Pilot your ship and destroy asteroids! How long can you survive?',
            'sort_order': 'desc',  # Higher score = better
        },
    ]

    def handle(self, *args, **options):
        # Create or get system user
        user, created = User.objects.get_or_create(
            email=self.SYSTEM_EMAIL,
            defaults={
                'is_active': True,
                'email_verified': True,
            }
        )
        if created:
            user.set_unusable_password()
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Created system user: {self.SYSTEM_EMAIL}'))
        else:
            self.stdout.write(f'System user already exists: {self.SYSTEM_EMAIL}')

        # Create or get demo game
        game, created = Game.objects.get_or_create(
            owner=user,
            slug=self.GAME_SLUG,
            defaults={
                'name': self.GAME_NAME,
                'description': 'Demo mini-games showcasing the Scores API',
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created game: {self.GAME_NAME}'))
        else:
            self.stdout.write(f'Game already exists: {self.GAME_NAME}')

        # Create leaderboards with fixed API tokens
        for lb_config in self.LEADERBOARDS:
            fixed_token = DEMO_API_TOKENS[lb_config['slug']]
            defaults = {
                'name': lb_config['name'],
                'description': lb_config['description'],
                'sort_order': lb_config['sort_order'],
            }
            # Add optional fields for correct_answer leaderboards
            if 'leaderboard_type' in lb_config:
                defaults['leaderboard_type'] = lb_config['leaderboard_type']
            if 'correct_answer' in lb_config:
                defaults['correct_answer'] = lb_config['correct_answer']

            leaderboard, created = Leaderboard.objects.get_or_create(
                game=game,
                slug=lb_config['slug'],
                defaults=defaults
            )
            if created:
                # Set the fixed token (bypassing the auto-generated one)
                leaderboard.api_token = fixed_token
                leaderboard.save(update_fields=['api_token'])
                self.stdout.write(self.style.SUCCESS(f'  Created leaderboard: {lb_config["name"]}'))
            else:
                # Ensure existing leaderboard has the correct fixed token
                if leaderboard.api_token != fixed_token:
                    leaderboard.api_token = fixed_token
                    leaderboard.save(update_fields=['api_token'])
                    self.stdout.write(f'  Updated token for: {lb_config["name"]}')
                else:
                    self.stdout.write(f'  Leaderboard already exists: {lb_config["name"]}')

        self.stdout.write(self.style.SUCCESS('\nDemo games setup complete!'))
        self.stdout.write(f'Public URL: /games/{self.GAME_SLUG}/')
