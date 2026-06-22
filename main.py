"""Foundational Chrome Dino Run clone built with Pygame sprites."""

from __future__ import annotations

from enum import Enum, auto
from pathlib import Path

import pygame


WINDOW_WIDTH = 800
WINDOW_HEIGHT = 400
FPS = 60

BACKGROUND_COLOR = (247, 247, 247)
OBJECT_COLOR = (83, 83, 83)
GROUND_Y = 300

BASE_DIR = Path(__file__).resolve().parent
ASSET_DIR = BASE_DIR / "assets"


class DinosaurState(Enum):
    """Current movement state for the dinosaur sprite."""

    RUNNING = auto()
    JUMPING = auto()
    DUCKING = auto()


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

        return {
            "running": running_sprites,
            "jumping": self._choose_jump_sprite(jump_sprite, start_sprite, running_sprites),
            "ducking": [
                self._load_image(asset_dir / "DinoDuck1.png"),
                self._load_image(asset_dir / "DinoDuck2.png"),
            ],
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

    def handle_event(self, event: pygame.event.Event) -> None:
        """Translate key presses and releases into player intent."""
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_SPACE, pygame.K_UP):
                self.jump()
            elif event.key == pygame.K_DOWN:
                self.down_key_held = True
        elif event.type == pygame.KEYUP and event.key == pygame.K_DOWN:
            self.down_key_held = False

    def jump(self) -> None:
        """Launch upward only when the dinosaur is touching the ground."""
        if not self.is_grounded():
            return

        self.velocity_y = -self.JUMP_VELOCITY
        self._set_state(DinosaurState.JUMPING)

    def is_grounded(self) -> bool:
        """Return whether the dinosaur's feet are aligned with the ground."""
        return self.rect.bottom >= self.ground_y and self.state != DinosaurState.JUMPING

    def update(self) -> None:
        """Advance physics, state selection, and animation by one frame."""
        if self.state == DinosaurState.JUMPING:
            self._apply_jump_physics()
        else:
            ground_state = (
                DinosaurState.DUCKING if self.down_key_held else DinosaurState.RUNNING
            )
            self._set_state(ground_state)

        self._advance_animation()

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
        if self.state == DinosaurState.JUMPING:
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
        bottom = self.ground_y if self.state != DinosaurState.JUMPING else self.rect.bottom

        self.image = next_image
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

        jumping_sprite = self.sprites["jumping"]
        assert isinstance(jumping_sprite, pygame.Surface)
        return jumping_sprite

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the current dinosaur sprite."""
        surface.blit(self.image, self.draw_rect)


class Game:
    """Top-level controller for window setup, events, updates, and drawing."""

    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Chrome Dino Run")
        self.clock = pygame.time.Clock()
        self.dinosaur = Dinosaur(GROUND_Y, ASSET_DIR)
        self.running = True

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
            else:
                self.dinosaur.handle_event(event)

    def update(self) -> None:
        """Update game objects in a deterministic order."""
        self.dinosaur.update()

    def draw(self) -> None:
        """Render a complete frame."""
        self.screen.fill(BACKGROUND_COLOR)
        pygame.draw.line(
            self.screen,
            OBJECT_COLOR,
            (0, GROUND_Y),
            (WINDOW_WIDTH, GROUND_Y),
            width=2,
        )
        self.dinosaur.draw(self.screen)
        pygame.display.flip()


def main() -> None:
    """Create and run the game application."""
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
