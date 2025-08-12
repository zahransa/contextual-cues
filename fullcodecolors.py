import pygame
import random
import time
import csv
import pandas as pd
import ast
import matplotlib.pyplot as plt
import sys
import serial
from statistics import mean
import os

# ========== CONFIGURATION ==========
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
TILE_SIZE = 50
FPS = 60
BLOCK_SIZE = 24
TRIALS_PATH = "contextual_trials_chun1998_black_FULL.csv"
PLOT_PATH_TEMPLATE = "summary_rt_plot_{subject}.png"
RESULTS_PATH_TEMPLATE = "results_chun1998_black_{subject}.csv"
VIBRESP_PATH_TEMPLATE = "vibration_responses_{subject}.csv"
STAIRCASE_TRIALS = 15
PORT = "COM4"
BAUDRATE = 115200
DEFAULT_ESTIMATED_RT = 0.7
STEP_SIZE = 1
MAX_INTENSITY = 10
MIN_INTENSITY = 2
VIBRATION_PROPORTION = 0.75

BACKGROUND_COLOR = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)  # kept for text; shapes use palette below

# --- Distractor/target colors (non-diagnostic), inspired by Chun & Jiang fig. ---
COLOR_PALETTE = [
    (235, 232, 82),   # yellow
    (236, 121, 86),   # orange
    (126, 196, 125),  # green
    (120, 190, 220)   # blue
]

# ========== INIT ==========
pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Contextual Cueing with Vibration")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 36)

try:
    arduino = serial.Serial(PORT, BAUDRATE, timeout=1)
    time.sleep(2)
except Exception:
    arduino = None
    print(f"WARNING: Could not open serial port {PORT}. Vibration disabled.")

# ========== UTILITIES ==========
def text_input(prompt):
    import tkinter as tk
    from tkinter import simpledialog
    root = tk.Tk()
    root.withdraw()
    return simpledialog.askstring("Input", prompt)

def display_text(surface, message, x, y):
    text = font.render(message, True, COLOR_BLACK)
    surface.blit(text, (x, y))

def send_vibration_intensity(intensity):
    if arduino:
        arduino.write(f"{intensity}".encode())

def log_response(response, intensity, phase, writer):
    writer.writerow({"response": response, "intensity": intensity, "phase": phase, "timestamp": time.time()})

# ========== STAIRCASE ==========
def run_staircase_procedure(csv_writer):
    trial_count = 0
    intensity = 5
    reversals = []
    previous_direction = None
    last_trial_time = time.time()
    random_interval = random.randint(1, 3)

    while trial_count < STAIRCASE_TRIALS:
        screen.fill(BACKGROUND_COLOR)
        display_text(screen, f"Staircase Trial {trial_count+1}/{STAIRCASE_TRIALS}", 100, 100)
        display_text(screen, "Press UP if you feel vibration", 100, 200)
        display_text(screen, "Don't press if not", 100, 240)
        pygame.display.flip()

        if time.time() - last_trial_time >= random_interval:
            send_vibration_intensity(intensity)
            last_trial_time = time.time()
            random_interval = random.randint(1, 3)
            trial_count += 1
            response = 0
            timeout = time.time() + 5

            while time.time() < timeout:
                for event in pygame.event.get():
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_UP:
                        response = 1
                        break
                if response:
                    break
                clock.tick(FPS)

            log_response(response, intensity, "staircase", csv_writer)

            direction = "down" if response else "up"
            new_intensity = max(MIN_INTENSITY, intensity - STEP_SIZE) if response else min(MAX_INTENSITY, intensity + STEP_SIZE)
            if previous_direction and previous_direction != direction:
                reversals.append(intensity)
            previous_direction = direction
            intensity = new_intensity

    threshold = sum(reversals[-6:]) / len(reversals[-6:]) if reversals else intensity

    screen.fill(BACKGROUND_COLOR)
    display_text(screen, f"Staircase Done. Threshold: {threshold:.2f}", 100, 250)
    display_text(screen, "Press any key to start the main task.", 100, 300)
    pygame.display.flip()
    while True:
        if any(event.type == pygame.KEYDOWN for event in pygame.event.get()):
            break
        clock.tick(FPS)

    return round(threshold + 0.5)

# ========== DRAWING ==========
def draw_shape(surface, shape, x, y, color):
    """Draw rotated T or L centered at (x, y)."""
    thickness = 5
    half = TILE_SIZE // 2

    if shape == 'T_left':
        pygame.draw.line(surface, color, (x, y - half), (x, y + half), thickness)  # stem
        pygame.draw.line(surface, color, (x - half, y), (x, y), thickness)         # bar left

    elif shape == 'T_right':
        pygame.draw.line(surface, color, (x, y - half), (x, y + half), thickness)  # stem
        pygame.draw.line(surface, color, (x, y), (x + half, y), thickness)         # bar right

    elif shape.startswith('L_'):
        tag = shape.split('_', 1)[1]  # 'ul','ur','dl','dr'
        if tag == 'ul':  # up + left
            pygame.draw.line(surface, color, (x, y), (x, y - TILE_SIZE), thickness)
            pygame.draw.line(surface, color, (x, y), (x - half, y), thickness)
        elif tag == 'ur':  # up + right
            pygame.draw.line(surface, color, (x, y), (x, y - TILE_SIZE), thickness)
            pygame.draw.line(surface, color, (x, y), (x + half, y), thickness)
        elif tag == 'dl':  # down + left
            pygame.draw.line(surface, color, (x, y), (x, y + TILE_SIZE), thickness)
            pygame.draw.line(surface, color, (x, y), (x - half, y), thickness)
        elif tag == 'dr':  # down + right
            pygame.draw.line(surface, color, (x, y), (x, y + TILE_SIZE), thickness)
            pygame.draw.line(surface, color, (x, y), (x + half, y), thickness)

# ========== CONTEXTUAL TASK ==========
def run_trial(trial, trial_num, rt_history, vibration_intensity, vibrate_this_trial, vibresp_writer):
    target_pos = ast.literal_eval(trial['target_pos'])
    distractors = ast.literal_eval(trial['distractors'])
    target_shape = trial['target_shape']
    is_old = trial['is_old']
    context_key = 'old' if is_old else 'new'

    tx, ty = target_pos
    x_target = tx * TILE_SIZE + 100
    y_target = ty * TILE_SIZE + 100

    # estimated RT determines vibration offset
    estimated_rt = mean(rt_history[context_key]) if rt_history[context_key] else DEFAULT_ESTIMATED_RT
    vibration_offset = max(estimated_rt - 0.1, 0.1)

    # --- Randomize L orientation & color every presentation ---
    L_ORIENTS = ['ul', 'ur', 'dl', 'dr']
    present_distractors = []
    for item in distractors:
        (dx, dy), _ = item  # ignore stored orient; reassign every trial
        ori = random.choice(L_ORIENTS)
        col = random.choice(COLOR_PALETTE)
        present_distractors.append((dx, dy, ori, col))

    # --- Target color from same palette (non-diagnostic) ---
    target_color = random.choice(COLOR_PALETTE)

    running = True
    response = None
    rt = None
    vibration_sent = False
    vibration_time = None
    vibration_response = False
    vibration_rt = None
    trial_start = time.time()
    vibration_time_abs = None
    k_up_time_abs = None

    while running:
        screen.fill(BACKGROUND_COLOR)
        now = time.time()

        # send vibration just before estimated response
        if vibrate_this_trial and not vibration_sent and now - trial_start >= vibration_offset:
            send_vibration_intensity(int(vibration_intensity))
            vibration_sent = True
            vibration_time = now - trial_start
            vibration_time_abs = time.time()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return 'INTERRUPT'
            elif event.type == pygame.KEYDOWN:
                if not response and event.key in [pygame.K_LEFT, pygame.K_RIGHT]:
                    response = 'T_right' if event.key == pygame.K_LEFT else 'T_left'
                    rt = time.time() - trial_start
                    running = False
                elif vibration_sent and event.key == pygame.K_UP:
                    k_up_time_abs = time.time()
                    vibration_response = True
                    if vibration_time_abs:
                        vibration_rt = k_up_time_abs - vibration_time_abs

        # draw scene (distractors first, then target)
        for (dx, dy, ori, col) in present_distractors:
            draw_shape(screen, f'L_{ori}', dx * TILE_SIZE + 100, dy * TILE_SIZE + 100, col)

        draw_shape(screen, target_shape, x_target, y_target, target_color)

        pygame.display.flip()
        clock.tick(FPS)

    if rt:
        rt_history[context_key].append(rt)

    if vibresp_writer:
        vibresp_writer.writerow({
            'trial_num': trial_num,
            'vibration_sent': vibrate_this_trial,
            'vibration_time_abs': vibration_time_abs,
            'k_up_time_abs': k_up_time_abs
        })

    return {
        'trial_num': trial_num,
        'context_id': trial['context_id'],
        'is_old': is_old,
        'target_shape': target_shape,
        'response': response,
        'correct': response == target_shape,
        'rt': round(rt, 3) if rt else None,
        'vibration_time': round(vibration_time, 3) if vibration_time else None,
        'rt_minus_vibration': round(rt - vibration_time, 3) if rt and vibration_time else None,
        'vibration_response': vibration_response,
        'vibration_rt': round(vibration_rt, 3) if vibration_rt else None
    }

def generate_summary_plot(results, subject):
    df = pd.DataFrame(results)
    df['epoch'] = df['trial_num'] // BLOCK_SIZE
    summary = df.groupby(['epoch', 'is_old'])['rt'].mean().reset_index()
    summary['label'] = summary['is_old'].map({True: 'Old Context', False: 'New Context'})
    plt.figure(figsize=(10, 6))
    for label, group in summary.groupby('label'):
        plt.plot(group['epoch'], group['rt'] * 1000, marker='o', label=label)
    plt.xlabel("Block")
    plt.ylabel("Search RT (ms)")
    plt.title(f"RT by Block - {subject}")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(PLOT_PATH_TEMPLATE.format(subject=subject))
    plt.close()

def show_message(message, wait_for_key=False):
    screen.fill(BACKGROUND_COLOR)
    lines = message.split("\n")
    for i, line in enumerate(lines):
        text = font.render(line, True, COLOR_BLACK)
        rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + i * 40))
        screen.blit(text, rect)
    pygame.display.flip()
    if wait_for_key:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN:
                    return
            clock.tick(FPS)
    else:
        time.sleep(2)

# ========== MAIN ==========
def main():
    subject = text_input("Enter subject ID:")
    if not subject:
        print("No subject ID entered. Exiting.")
        return

    trials_df = pd.read_csv(TRIALS_PATH)
    results = []
    rt_history = {'old': [], 'new': []}

    # Run Staircase
    staircase_file = open(f"staircase_results_{subject}.csv", "w", newline='')
    writer = csv.DictWriter(staircase_file, fieldnames=["response", "intensity", "phase", "timestamp"])
    writer.writeheader()
    threshold = run_staircase_procedure(writer)
    staircase_file.close()

    # Prepare vibration response logger
    vibresp_file = open(VIBRESP_PATH_TEMPLATE.format(subject=subject), "w", newline='')
    vibresp_writer = csv.DictWriter(vibresp_file, fieldnames=["trial_num", "vibration_sent", "vibration_time_abs", "k_up_time_abs"])
    vibresp_writer.writeheader()

    show_message("Contextual Cueing Task Starting\nPress LEFT/RIGHT for T orientation\nPress UP if you feel vibration", wait_for_key=True)

    total_trials = len(trials_df)
    vibration_trials = random.sample(range(total_trials), int(total_trials * VIBRATION_PROPORTION))

    for i, row in trials_df.iterrows():
        if i % BLOCK_SIZE == 0 and i > 0:
            block_df = pd.DataFrame(results[-BLOCK_SIZE:])
            avg_rt = block_df['rt'].mean()
            acc = block_df['correct'].mean() * 100
            show_message(f"Block {i // BLOCK_SIZE} complete\nAvg RT: {avg_rt:.2f}s, Accuracy: {acc:.1f}%", wait_for_key=True)

        vibrate_now = i in vibration_trials
        result = run_trial(row, i, rt_history, threshold, vibrate_now, vibresp_writer)
        if result == 'INTERRUPT':
            break
        results.append(result)

    vibresp_file.close()

    if results:
        results_path = RESULTS_PATH_TEMPLATE.format(subject=subject)
        with open(results_path, "w", newline='') as file:
            fieldnames = ['trial_num', 'context_id', 'is_old', 'target_shape', 'response', 'correct',
                          'rt', 'vibration_time', 'rt_minus_vibration', 'vibration_response', 'vibration_rt']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        generate_summary_plot(results, subject)

    show_message("Experiment complete. Thank you!")
    pygame.quit()

if __name__ == "__main__":
    main()
