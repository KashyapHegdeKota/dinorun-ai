"""Foundational Chrome Dino Run clone built with Pygame.

This module intentionally focuses on the first production-ready slice of the
game: window setup, a stable main loop, ground rendering, and responsive
dinosaur jump physics.
"""

from __future__ import annotations

import pygame


WINDOW_WIDTH = 800
WINDOW_HEIGHT = 400
FPS = 60

BACKGROUND_COLOR = (247, 247, 247)
OBJECT_COLOR = (83, 83, 83)

GROUND_Y = 300


class Dinosaur:
    """Player-controlled dinosaur with simple vertical jump physics."""

    WIDTH = 40
    HEIGHT = 40
    START_X = 50
    JUMP_VELOCITY = 15
    GRAVITY = 0.8

    def __init__(self, ground_y: int) -> None:
        self.ground_y = ground_y
        self.rect = pygame.Rect(
            self.START_X,
            self.ground_y - self.HEIGHT,
            self.WIDTH,
            self.HEIGHT,
        )
        self.velocity_y = 0.0
        self.is_jumping = False

    def handle_event(self, event: pygame.event.Event) -> None:
        """Start a jump when requested, but only while grounded."""
        if event.type != pygame.KEYDOWN:
            return

        if event.key in (pygame.K_SPACE, pygame.K_UP) and not self.is_jumping:
            self.jump()

    def jump(self) -> None:
        """Launch the dinosaur upward by setting its initial vertical speed."""
        self.velocity_y = -self.JUMP_VELOCITY
        self.is_jumping = True

    def update(self) -> None:
        """Advance the dinosaur physics by one frame."""
        if not self.is_jumping:
            return

        # Move first using the current velocity, then apply gravity so the
        # upward motion eases out naturally and transitions into falling.
        self.rect.y += int(self.velocity_y)
        self.velocity_y += self.GRAVITY

        # Clamp the player back to the ground line to avoid sinking below it
        # after gravity pulls the rectangle past the landing point.
        ground_top = self.ground_y - self.HEIGHT
        if self.rect.y >= ground_top:
            self.rect.y = ground_top
            self.velocity_y = 0.0
            self.is_jumping = False

    def draw(self, surface: pygame.Surface) -> None:
        """Render the placeholder dinosaur rectangle."""
        pygame.draw.rect(surface, OBJECT_COLOR, self.rect)


class Game:
    """Top-level controller for window setup, events, updates, and drawing."""

    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Chrome Dino Run")
        self.clock = pygame.time.Clock()
        self.dinosaur = Dinosaur(GROUND_Y)
        self.running = True

    def run(self) -> None:
        """Execute the locked 60 FPS game loop."""
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)

        pygame.quit()

    def handle_events(self) -> None:
        """Process window events and route player input."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            else:
                self.dinosaur.handle_event(event)

    def update(self) -> None:
        """Update every active game object in sequence."""
        self.dinosaur.update()

    def draw(self) -> None:
        """Draw the full frame using the classic Chrome Dino palette."""
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
    """Create and run the game."""
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
