import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import math
from noise import pnoise2

# Constants
WORLD_SIZE = 100
BLOCK_SIZE = 2
GRAVITY = 0.08
JUMP_SPEED = 0.6
FLOOR_HEIGHT = 1
CAMERA_SPEED = 0.15
MOUSE_SENSITIVITY = 0.2
FOV = 60
SPRINT_MULTIPLIER = 2
CROUCH_MULTIPLIER = 0.5
DAY_DURATION = 120  # 120 seconds for full day-night cycle
MAX_LIGHT_INTENSITY = 1.0
MIN_LIGHT_INTENSITY = 0.1

# Block types
block_types = {
    'grass': 1,
    'stone': 2,
    'dirt': 3,
    'sand': 4,
    'water': 5
}
inventory = list(block_types.keys())
selected_block = 0

# Player states
is_sprinting = False
is_crouching = False

# Load and bind texture from file
def load_texture(file):
    texture_surface = pygame.image.load(file)
    texture_data = pygame.image.tostring(texture_surface, "RGB", 1)
    width, height = texture_surface.get_size()

    tex_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, width, height, 0, GL_RGB, GL_UNSIGNED_BYTE, texture_data)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    return tex_id

# Function to draw a textured cube
def draw_cube(texture):
    glBindTexture(GL_TEXTURE_2D, texture)
    glBegin(GL_QUADS)
    for face in faces:
        for vertex in face:
            glTexCoord2f(vertex % 2, (vertex // 2) % 2)  # Simple 2D texture mapping
            glVertex3fv(vertices[vertex])
    glEnd()

# Procedural Terrain Generation
def generate_terrain():
    terrain = np.zeros((WORLD_SIZE, WORLD_SIZE), dtype=int)
    scale = 50.0
    octaves = 6
    persistence = 0.5
    lacunarity = 2.0

    for x in range(WORLD_SIZE):
        for z in range(WORLD_SIZE):
            # Generate height using Perlin noise
            height = int(pnoise2(x / scale, z / scale, octaves=octaves, persistence=persistence, lacunarity=lacunarity) * 10 + 10)
            terrain[x][z] = height

    return terrain

# Function to create the world
def create_world(terrain):
    world = np.zeros((WORLD_SIZE, WORLD_SIZE, 20), dtype=int)
    for x in range(WORLD_SIZE):
        for z in range(WORLD_SIZE):
            height = terrain[x][z]
            for y in range(height):
                if y < height - 2:
                    world[x][y][z] = block_types['stone']  # Below ground level is stone
                elif y < height - 1:
                    world[x][y][z] = block_types['dirt']   # Dirt layer
                else:
                    world[x][y][z] = block_types['grass']  # Top is grass
    return world

# Render the world
def render_world(world, textures):
    glEnable(GL_TEXTURE_2D)
    for x in range(WORLD_SIZE):
        for y in range(20):
            for z in range(WORLD_SIZE):
                block = world[x][y][z]
                if block != 0:  # If there's a block here
                    glPushMatrix()
                    glTranslatef(x * BLOCK_SIZE, y * BLOCK_SIZE, z * BLOCK_SIZE)
                    draw_cube(textures[block])
                    glPopMatrix()

# Lighting for Day-Night Cycle
def set_lighting(time_of_day):
    light_intensity = MAX_LIGHT_INTENSITY * math.sin(math.pi * time_of_day / DAY_DURATION) + MIN_LIGHT_INTENSITY
    glLightfv(GL_LIGHT0, GL_DIFFUSE, [light_intensity, light_intensity, light_intensity, 1.0])
    glLightfv(GL_LIGHT0, GL_AMBIENT, [0.3, 0.3, 0.3, 1.0])

# Player class with advanced mechanics
class Player:
    def __init__(self):
        self.x, self.y, self.z = 50, 50, 50
        self.y_velocity = 0
        self.on_ground = False
        self.pitch, self.yaw = 0, 0
        self.fov = FOV

    def apply_gravity(self, world):
        if not self.on_ground:
            self.y_velocity -= GRAVITY
        self.y += self.y_velocity

        # Stop falling if on ground
        if self.y <= FLOOR_HEIGHT:
            self.y = FLOOR_HEIGHT
            self.y_velocity = 0
            self.on_ground = True
        else:
            self.on_ground = False

    def jump(self):
        if self.on_ground:
            self.y_velocity = JUMP_SPEED
            self.on_ground = False

    def move(self, direction, world):
        global is_sprinting, is_crouching
        speed = CAMERA_SPEED
        if is_sprinting:
            speed *= SPRINT_MULTIPLIER
        elif is_crouching:
            speed *= CROUCH_MULTIPLIER

        # Calculate movement vectors
        move_x = direction[0] * math.cos(math.radians(self.yaw)) - direction[2] * math.sin(math.radians(self.yaw))
        move_z = direction[0] * math.sin(math.radians(self.yaw)) + direction[2] * math.cos(math.radians(self.yaw))

        if not check_collision((self.x + move_x, self.y, self.z + move_z), world):
            self.x += move_x * speed
            self.z += move_z * speed

    def rotate(self, dx, dy):
        self.yaw += dx * MOUSE_SENSITIVITY
        self.pitch += dy * MOUSE_SENSITIVITY
        self.pitch = max(-89, min(89, self.pitch))

    def get_view_matrix(self):
        look_x = math.cos(math.radians(self.pitch)) * math.cos(math.radians(self.yaw))
        look_y = math.sin(math.radians(self.pitch))
        look_z = math.cos(math.radians(self.pitch)) * math.sin(math.radians(self.yaw))
        return (self.x, self.y, self.z), (self.x + look_x, self.y + look_y, self.z + look_z)

# Main function to run the game loop
def main():
    pygame.init()
    display = (1280, 720)
    pygame.display.set_mode(display, DOUBLEBUF | OPENGL)
    gluPerspective(FOV, (display[0] / display[1]), 0.1, 1000.0)
    glTranslatef(0, 0, -20)

    # Load textures
    textures = {
        block_types['grass']: load_texture('block_grass.png'),
        block_types['stone']: load_texture('block_stone.png'),
        block_types['dirt']: load_texture('block_dirt.png'),
        block_types['sand']: load_texture('block_sand.png'),
        block_types['water']: load_texture('block_water.png')
    }

    terrain = generate_terrain()  # Generate terrain
    world = create_world(terrain)  # Create the world
    player = Player()  # Create player

    pygame.event.set_grab(True)
    pygame.mouse.set_visible(False)

    clock = pygame.time.Clock()

    day_time = 0  # Initialize day-night cycle

    # Main game loop
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                quit()

        keys = pygame.key.get_pressed()

        # Movement
        direction = [0, 0, 0]
        if keys[K_w]:
            direction[2] = -1
        if keys[K_s]:
            direction[2] = 1
        if keys[K_a]:
            direction[0] = -1
        if keys[K_d]:
            direction[0] = 1
        player.move(direction, world)

        # Sprinting and crouching
        global is_sprinting, is_crouching
        is_sprinting = keys[K_LSHIFT]
        is_crouching = keys[K_LCTRL]

        # Jump
        if keys[K_SPACE]:
            player.jump()

        # Mouse movement for camera control
        dx, dy = pygame.mouse.get_rel()
        player.rotate(dx, dy)

        # Apply gravity
        player.apply_gravity(world)

        # Day-night cycle
        day_time = (day_time + 1) % DAY_DURATION
        set_lighting(day_time)

        # Clear screen and render world
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        # Get player view matrix
        camera_pos, camera_look = player.get_view_matrix()
        gluLookAt(*camera_pos, *camera_look, 0, 1, 0)

        render_world(world, textures)

        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()
