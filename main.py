"""Foundational Chrome Dino Run clone built with Pygame sprites."""

from __future__ import annotations

from enum import Enum, auto
from pathlib import Path

import random

import pygame

WINDOW_WIDTH = 800
WINDOW_HEIGHT = 400
FPS = 60

BACKGROUND_COLOR = (247, 247, 247)
OBJECT_COLOR = (83, 83, 83)
GROUND_Y = 300

BASE_DIR = Path(__file__).resolve().parent
ASSET_DIR = BASE_DIR / "assets"

CLOUD_SPEED = 2
CLOUD_MIN_Y = 12
CLOUD_MAX_Y = 24
CLOUD_SPAWN_INTERVAL = 170
CLOUD_SPAWN_JITTER = 30
CLOUD_MAX_COUNT = 3

INITIAL_GAME_SPEED = 8.0
SPEED_ACCELERATION_PER_FRAME = 0.002
SCORE_INCREMENT_SCALE = 0.025
OBSTACLE_MIN_GAP_PIXELS = 420
OBSTACLE_MAX_GAP_PIXELS = 720
OBSTACLE_MIN_SAFE_FRAMES = 50
OBSTACLE_MAX_SAFE_FRAMES = 85
FIRST_OBSTACLE_DELAY_FRAMES = 60

CACTUS_ASSET_FILES = {
    "large": ["LargeCactus1.png", "LargeCactus2.png", "LargeCactus3.png"],
    "small": ["SmallCactus1.png", "SmallCactus2.png", "SmallCactus3.png"],
}


class DinosaurState(Enum):
    """Current movement state for the dinosaur sprite."""

    RUNNING = auto()
    JUMPING = auto()
    DUCKING = auto()
    DEAD = auto()


class Dinosaur:
    """Player-controlled dinosaur with sprite animation and jump physics."""

    START_X = 50
    JUMP_VELOCITY = 15
    GRAVITY = 0.8
    ANIMATION_SWITCH_FRAMES = 10

    def __init__(self, ground_y: int, asset_dir: Path) -> None:
        self.ground_y = ground_y
        self.sprites = self._load_sprites(asset_dir)

        self.state = DinosaurState.RUNNING
        self.animation_frame = 0
        self.animation_counter = 0
        self.velocity_y = 0.0
        self.position_y = 0.0
        self.down_key_held = False

        self.image = self.sprites["running"][self.animation_frame]
        self.mask = pygame.mask.from_surface(self.image)
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.draw_rect = self.image.get_rect()
        self._place_sprite(self.START_X, self.ground_y)
        self.position_y = float(self.rect.y)

    def _load_sprites(self, asset_dir: Path) -> dict[str, pygame.Surface | list[pygame.Surface]]:
        """Load every required dinosaur image from disk."""
        running_sprites = [
            self._load_image(asset_dir / "DinoRun1.png"),
            self._load_image(asset_dir / "DinoRun2.png"),
        ]
        jump_sprite = self._load_image(asset_dir / "DinoJump.png")
        start_sprite = self._load_image(asset_dir / "DinoStart.png")
        duck_sprites = self._choose_duck_sprites(
            [
                self._load_image(asset_dir / "DinoDuck1.png"),
                self._load_image(asset_dir / "DinoDuck2.png"),
            ],
            running_sprites,
        )

        return {
            "running": running_sprites,
            "jumping": self._choose_jump_sprite(jump_sprite, start_sprite, running_sprites),
            "ducking": duck_sprites,
            "dead": self._load_image(asset_dir / "DinoDead.png"),
            "start": start_sprite,
        }

    @staticmethod
    def _load_image(path: Path) -> pygame.Surface:
        """Load a sprite image and preserve PNG transparency."""
        try:
            return pygame.image.load(str(path)).convert_alpha()
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Missing required sprite asset: {path}") from exc
        except pygame.error as exc:
            raise RuntimeError(f"Unable to load sprite asset: {path}") from exc

    @staticmethod
    def _choose_jump_sprite(
        jump_sprite: pygame.Surface,
        start_sprite: pygame.Surface,
        running_sprites: list[pygame.Surface],
    ) -> pygame.Surface:
        """Use an upright jump pose if the configured jump PNG is duck-sized."""
        jump_bounds = jump_sprite.get_bounding_rect()
        run_height = max(sprite.get_bounding_rect().height for sprite in running_sprites)

        # Some asset packs accidentally ship DinoJump.png as a ducking frame.
        # A jump pose should be roughly as tall as the running pose; otherwise
        # the dinosaur appears to duck while airborne.
        if jump_bounds.height < run_height * 0.8:
            return start_sprite

        return jump_sprite

    @staticmethod
    def _choose_duck_sprites(
        duck_sprites: list[pygame.Surface],
        running_sprites: list[pygame.Surface],
    ) -> list[pygame.Surface]:
        """Keep duck animation frames low so holding Down never pops upright."""
        run_height = max(sprite.get_bounding_rect().height for sprite in running_sprites)
        low_profile_frames = [
            sprite
            for sprite in duck_sprites
            if sprite.get_bounding_rect().height < run_height * 0.8
        ]

        # This asset set has DinoDuck1.png mislabeled as an upright frame.
        # If only one true duck frame exists, reuse it for both animation slots
        # so the state remains visually stable while Down is held.
        if len(low_profile_frames) == 1:
            return [low_profile_frames[0], low_profile_frames[0]]

        if len(low_profile_frames) >= 2:
            return low_profile_frames[:2]

        return duck_sprites

    def handle_event(self, event: pygame.event.Event) -> None:
        """Translate key presses and releases into player intent."""
        if self.state == DinosaurState.DEAD:
            return

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_SPACE, pygame.K_UP):
                self.jump()
            elif event.key == pygame.K_DOWN:
                self.down_key_held = True
        elif event.type == pygame.KEYUP and event.key == pygame.K_DOWN:
            self.down_key_held = False

    def jump(self) -> None:
        """Launch upward only when the dinosaur is touching the ground."""
        if self.state == DinosaurState.DEAD:
            return

        if not self.is_grounded():
            return

        self.velocity_y = -self.JUMP_VELOCITY
        self._set_state(DinosaurState.JUMPING)

    def is_grounded(self) -> bool:
        """Return whether the dinosaur's feet are aligned with the ground."""
        return self.rect.bottom >= self.ground_y and self.state != DinosaurState.JUMPING

    def update(self, pressed_keys: pygame.key.ScancodeWrapper | None = None) -> None:
        """Advance physics, state selection, and animation by one frame."""
        if self.state == DinosaurState.DEAD:
            self._sync_image_and_hitbox()
            return

        if pressed_keys is not None:
            self.down_key_held = pressed_keys[pygame.K_DOWN]

        if self.state == DinosaurState.JUMPING:
            self._apply_jump_physics()
        else:
            ground_state = (
                DinosaurState.DUCKING if self.down_key_held else DinosaurState.RUNNING
            )
            self._set_state(ground_state)

        self._advance_animation()

    def die(self) -> None:
        """Switch to the dead sprite and stop all player motion."""
        self.velocity_y = 0.0
        self.down_key_held = False
        self._set_state(DinosaurState.DEAD)

    def reset(self) -> None:
        """Restore the dinosaur to its initial grounded running state."""
        self.state = DinosaurState.RUNNING
        self.animation_frame = 0
        self.animation_counter = 0
        self.velocity_y = 0.0
        self.down_key_held = False
        running_sprites = self.sprites["running"]
        assert isinstance(running_sprites, list)
        self.image = running_sprites[self.animation_frame]
        self.mask = pygame.mask.from_surface(self.image)
        self._place_sprite(self.START_X, self.ground_y)
        self.position_y = float(self.rect.y)

    def _apply_jump_physics(self) -> None:
        """Move vertically using velocity, then accelerate downward."""
        # Negative velocity moves the sprite upward because screen-space Y grows
        # downward. Gravity increases velocity each frame until the dino falls.
        self.position_y += self.velocity_y
        self.velocity_y += self.GRAVITY
        self.rect.y = round(self.position_y)
        self._sync_draw_rect_to_hitbox()

        # Clamp to the ground when landing so accumulated velocity cannot push
        # the feet below the floor line.
        if self.rect.bottom >= self.ground_y:
            self.rect.bottom = self.ground_y
            self.position_y = float(self.rect.y)
            self.velocity_y = 0.0
            next_state = (
                DinosaurState.DUCKING if self.down_key_held else DinosaurState.RUNNING
            )
            self._set_state(next_state)

    def _set_state(self, new_state: DinosaurState) -> None:
        """Switch state and reset animation when entering a new movement mode."""
        if self.state == new_state:
            return

        self.state = new_state
        self.animation_frame = 0
        self.animation_counter = 0
        self._sync_image_and_hitbox()

    def _advance_animation(self) -> None:
        """Toggle running and ducking sprites every fixed number of frames."""
        if self.state in (DinosaurState.JUMPING, DinosaurState.DEAD):
            self._sync_image_and_hitbox()
            return

        self.animation_counter += 1
        if self.animation_counter < self.ANIMATION_SWITCH_FRAMES:
            return

        self.animation_counter = 0
        self.animation_frame = (self.animation_frame + 1) % 2
        self._sync_image_and_hitbox()

    def _sync_image_and_hitbox(self) -> None:
        """Match the active sprite and collision rectangle to the current state."""
        next_image = self._get_current_image()
        if next_image is self.image:
            self._sync_draw_rect_to_hitbox()
            return

        left = self.rect.left
        bottom = self.ground_y
        if self.state in (DinosaurState.JUMPING, DinosaurState.DEAD):
            bottom = self.rect.bottom

        self.image = next_image
        self.mask = pygame.mask.from_surface(self.image)
        self._place_sprite(left, bottom)
        self.position_y = float(self.rect.y)

    def _place_sprite(self, hitbox_left: int, hitbox_bottom: int) -> None:
        """Place visible sprite pixels at the requested hitbox coordinates."""
        bounds = self._visible_sprite_bounds()

        self.rect = pygame.Rect(
            hitbox_left,
            hitbox_bottom - bounds.height,
            bounds.width,
            bounds.height,
        )
        self._sync_draw_rect_to_hitbox()

    def _sync_draw_rect_to_hitbox(self) -> None:
        """Position the PNG canvas so its visible pixels wrap the hitbox."""
        bounds = self._visible_sprite_bounds()
        self.draw_rect = self.image.get_rect()
        self.draw_rect.left = self.rect.left - bounds.left
        self.draw_rect.top = self.rect.top - bounds.top

    def _visible_sprite_bounds(self) -> pygame.Rect:
        """Return the non-transparent sprite bounds used for collision sizing."""
        bounds = self.image.get_bounding_rect()
        if bounds.width == 0 or bounds.height == 0:
            return self.image.get_rect()
        return bounds

    def _get_current_image(self) -> pygame.Surface:
        """Choose the sprite that should be visible for the current state."""
        if self.state == DinosaurState.RUNNING:
            running_sprites = self.sprites["running"]
            assert isinstance(running_sprites, list)
            return running_sprites[self.animation_frame]

        if self.state == DinosaurState.DUCKING:
            ducking_sprites = self.sprites["ducking"]
            assert isinstance(ducking_sprites, list)
            return ducking_sprites[self.animation_frame]

        if self.state == DinosaurState.DEAD:
            dead_sprite = self.sprites["dead"]
            assert isinstance(dead_sprite, pygame.Surface)
            return dead_sprite

        jumping_sprite = self.sprites["jumping"]
        assert isinstance(jumping_sprite, pygame.Surface)
        return jumping_sprite

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the current dinosaur sprite."""
        surface.blit(self.image, self.draw_rect)


class Cloud:
    """Slow-moving background cloud with paced spawning handled by Game."""

    def __init__(self, image: pygame.Surface) -> None:
        self.image = image
        self.x = float(WINDOW_WIDTH + random.randint(20, 120))
        self.y = random.randint(CLOUD_MIN_Y, CLOUD_MAX_Y)
        self.rect = self.image.get_rect(topleft=(round(self.x), self.y))

    def update(self) -> None:
        """Move left slowly so clouds feel like background scenery."""
        self.x -= CLOUD_SPEED
        self.rect.x = round(self.x)

    def is_off_screen(self) -> bool:
        """Return whether the cloud has fully left the viewport."""
        return self.rect.right < 0

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the cloud behind gameplay objects."""
        surface.blit(self.image, self.rect)


class Cactus:
    """Asset-driven cactus obstacle with a tight visible-pixel hitbox."""

    HITBOX_INSET_X = 10
    HITBOX_INSET_Y = 6

    def __init__(self, image: pygame.Surface) -> None:
        self.image = image
        self.mask = pygame.mask.from_surface(self.image)
        self.bounds = self._visible_sprite_bounds()
        self.x = float(WINDOW_WIDTH + random.randint(20, 80))

        # The visible rect tracks non-transparent pixels. The collision rect is
        # then inset from that visible body so tiny edge pixels do not cause
        # harsh early crashes.
        self.visible_rect = pygame.Rect(0, 0, self.bounds.width, self.bounds.height)
        self.rect = self.visible_rect.copy()
        self.draw_rect = self.image.get_rect()
        self._sync_rects()

    def _visible_sprite_bounds(self) -> pygame.Rect:
        """Return non-transparent sprite bounds for collision and grounding."""
        bounds = self.image.get_bounding_rect()
        if bounds.width == 0 or bounds.height == 0:
            return self.image.get_rect()
        return bounds

    def update(self, game_speed: float) -> None:
        """Move the cactus smoothly toward the dinosaur at obstacle speed."""
        self.x -= game_speed
        self._sync_rects()

    def _sync_rects(self) -> None:
        """Maintain visible pixels, tightened hitbox, and PNG canvas offsets."""
        self.visible_rect.left = round(self.x)
        self.visible_rect.bottom = GROUND_Y

        self.rect = self.visible_rect.copy()
        self.rect.inflate_ip(-self.HITBOX_INSET_X, -self.HITBOX_INSET_Y)
        self.rect.bottom = GROUND_Y

        self.draw_rect.left = self.visible_rect.left - self.bounds.left
        self.draw_rect.top = self.visible_rect.top - self.bounds.top

    def is_off_screen(self) -> bool:
        """Return whether the visible cactus pixels have left the viewport."""
        return self.visible_rect.right < 0

    def draw(self, surface: pygame.Surface) -> None:
        """Blit the exact cactus PNG at its current world position."""
        surface.blit(self.image, self.draw_rect)


class Game:
    """Top-level controller for window setup, events, updates, and drawing."""

    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Chrome Dino Run")
        self.clock = pygame.time.Clock()
        self.score_font = pygame.font.SysFont("consolas", 24, bold=True)
        self.game_over_font = pygame.font.SysFont("consolas", 36, bold=True)
        self.cloud_image = self._load_image(ASSET_DIR / "Cloud.png")
        self.cactus_images = self._load_cactus_images(ASSET_DIR)
        self.dinosaur = Dinosaur(GROUND_Y, ASSET_DIR)
        self.running = True
        self.game_over = False
        self.game_speed = INITIAL_GAME_SPEED
        self.score = 0.0
        self.high_score = 0
        self.clouds: list[Cloud] = []
        self.obstacles: list[Cactus] = []
        self.cloud_spawn_timer = 20
        self.obstacle_spawn_timer = FIRST_OBSTACLE_DELAY_FRAMES

    @staticmethod
    def _load_image(path: Path) -> pygame.Surface:
        """Load an image once, preserving PNG transparency."""
        try:
            return pygame.image.load(str(path)).convert_alpha()
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Missing required sprite asset: {path}") from exc
        except pygame.error as exc:
            raise RuntimeError(f"Unable to load sprite asset: {path}") from exc

    def _load_cactus_images(self, asset_dir: Path) -> dict[str, list[pygame.Surface]]:
        """Pre-load cactus variants so gameplay never rereads image files."""
        return {
            group_name: [
                self._load_image(asset_dir / file_name)
                for file_name in file_names
            ]
            for group_name, file_names in CACTUS_ASSET_FILES.items()
        }

    def run(self) -> None:
        """Execute the main loop at a locked 60 FPS."""
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)

        pygame.quit()

    def handle_events(self) -> None:
        """Process OS events and route gameplay input."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif self.game_over:
                if event.type == pygame.KEYDOWN and event.key in (
                    pygame.K_SPACE,
                    pygame.K_UP,
                ):
                    self.reset_game()
            else:
                self.dinosaur.handle_event(event)

    def update(self) -> None:
        """Update game objects in a deterministic order."""
        if self.game_over:
            return

        pressed_keys = pygame.key.get_pressed()
        self.dinosaur.update(pressed_keys)
        self._update_score_and_speed()
        self._update_clouds()
        self._update_obstacles()
        self._check_collisions()

    def _update_score_and_speed(self) -> None:
        """Increase score and gradually accelerate the game each active frame."""
        self.score += self.game_speed * SCORE_INCREMENT_SCALE
        self.high_score = max(self.high_score, int(self.score))
        self.game_speed += SPEED_ACCELERATION_PER_FRAME

    def _update_clouds(self) -> None:
        """Spawn clouds at a steady pace and remove old ones."""
        self.cloud_spawn_timer -= 1
        if self.cloud_spawn_timer <= 0 and len(self.clouds) < CLOUD_MAX_COUNT:
            self.clouds.append(Cloud(self.cloud_image))
            self._reset_cloud_spawn_timer()

        for cloud in self.clouds:
            cloud.update()

        self.clouds = [cloud for cloud in self.clouds if not cloud.is_off_screen()]

    def _reset_cloud_spawn_timer(self) -> None:
        """Schedule the next cloud with light jitter instead of wild gaps."""
        self.cloud_spawn_timer = CLOUD_SPAWN_INTERVAL + random.randint(
            -CLOUD_SPAWN_JITTER,
            CLOUD_SPAWN_JITTER,
        )

    def _update_obstacles(self) -> None:
        """Spawn and move cactus obstacles across the ground."""
        self.obstacle_spawn_timer -= 1
        if self.obstacle_spawn_timer <= 0:
            self.obstacles.append(Cactus(self._select_cactus_image()))
            self.obstacle_spawn_timer = self._next_obstacle_spawn_frames()

        for obstacle in self.obstacles:
            obstacle.update(self.game_speed)

        self.obstacles = [
            obstacle for obstacle in self.obstacles if not obstacle.is_off_screen()
        ]

    def _next_obstacle_spawn_frames(self) -> int:
        """Convert a safe pixel gap into frames at the current game speed."""
        min_gap_pixels = max(
            OBSTACLE_MIN_GAP_PIXELS,
            self.game_speed * OBSTACLE_MIN_SAFE_FRAMES,
        )
        max_gap_pixels = max(
            OBSTACLE_MAX_GAP_PIXELS,
            self.game_speed * OBSTACLE_MAX_SAFE_FRAMES,
        )
        gap_pixels = random.uniform(min_gap_pixels, max_gap_pixels)
        return max(1, round(gap_pixels / self.game_speed))

    def _select_cactus_image(self) -> pygame.Surface:
        """Choose a large or small cactus group, then one of its three variants."""
        group_name = random.choice(("large", "small"))
        return random.choice(self.cactus_images[group_name])

    def _check_collisions(self) -> None:
        """End the current run when solid dinosaur and cactus pixels overlap."""
        for obstacle in self.obstacles:
            # Masks are generated from the full PNG canvases, so their offset
            # must use draw_rect positions rather than the debug hitbox rects.
            offset = (
                obstacle.draw_rect.x - self.dinosaur.draw_rect.x,
                obstacle.draw_rect.y - self.dinosaur.draw_rect.y,
            )
            if self.dinosaur.mask.overlap(obstacle.mask, offset) is not None:
                self._trigger_game_over()
                return

    def _trigger_game_over(self) -> None:
        """Freeze gameplay and put the dinosaur into its dead sprite state."""
        self.game_over = True
        self.high_score = max(self.high_score, int(self.score))
        self.dinosaur.die()

    def reset_game(self) -> None:
        """Start a fresh run while preserving the session high score."""
        self.game_over = False
        self.game_speed = INITIAL_GAME_SPEED
        self.score = 0.0
        self.clouds.clear()
        self.obstacles.clear()
        self.cloud_spawn_timer = 20
        self.obstacle_spawn_timer = FIRST_OBSTACLE_DELAY_FRAMES
        self.dinosaur.reset()

    def draw(self) -> None:
        """Render a complete frame."""
        self.screen.fill(BACKGROUND_COLOR)
        for cloud in self.clouds:
            cloud.draw(self.screen)

        pygame.draw.line(
            self.screen,
            OBJECT_COLOR,
            (0, GROUND_Y),
            (WINDOW_WIDTH, GROUND_Y),
            width=2,
        )
        for obstacle in self.obstacles:
            obstacle.draw(self.screen)

        self.dinosaur.draw(self.screen)
        self._draw_score()
        if self.game_over:
            self._draw_game_over()
        # Draw a red border around the Dino's hitbox
        pygame.draw.rect(self.screen, (255, 0, 0), self.dinosaur.rect, 2)

        # Draw a blue border around every active cactus hitbox
        for obstacle in self.obstacles:
            pygame.draw.rect(self.screen, (0, 0, 255), obstacle.rect, 2)
        pygame.display.flip()

    def _draw_score(self) -> None:
        """Render high score and current score in the top-right corner."""
        score_text = f"HI {self.high_score:05d}  {int(self.score):05d}"
        score_surface = self.score_font.render(score_text, True, OBJECT_COLOR)
        score_rect = score_surface.get_rect(topright=(WINDOW_WIDTH - 20, 20))
        self.screen.blit(score_surface, score_rect)

    def _draw_game_over(self) -> None:
        """Render the centered game-over prompt after a collision."""
        message = self.game_over_font.render("GAME OVER", True, OBJECT_COLOR)
        message_rect = message.get_rect(
            center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 20)
        )
        self.screen.blit(message, message_rect)

        prompt = self.score_font.render(
            "PRESS SPACE OR UP TO RESTART",
            True,
            OBJECT_COLOR,
        )
        prompt_rect = prompt.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 25))
        self.screen.blit(prompt, prompt_rect)


def main() -> None:
    """Create and run the game application."""
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
