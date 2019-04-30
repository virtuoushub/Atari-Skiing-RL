from typing import Union

import gym
import numpy as np
import matplotlib.pyplot as plt
from collections import deque
from keras.optimizers import RMSprop

from agent import e_greedy_policy_action, DQN
from model import atari_skiing_model
from utils import create_path, atari_preprocess


def create_skiing_environment():
    """
    Creates a skiing environment.

    :return: the skiing environment, the initial state, the image's height and width and the action space's size.
    """
    # Create the skiing environment.
    environment = gym.make('Skiing-v0')
    # Reset the environment and get the initial state.
    init_state = environment.reset()
    # Get the observation space's height and width.
    height, width = environment.observation_space.shape[0], environment.observation_space.shape[1]
    # Get the number of possible moves.
    act_space_size = environment.action_space.n

    return environment, init_state, height, width, act_space_size


def render_frame() -> None:
    """ Renders a frame, only if the user has chosen to do so. """
    if render:
        env.render()


def game_loop() -> None:
    """ Starts the game loop and trains the agent. """
    # Run for a number of episodes.
    for episode in range(nEpisodes):
        # Init vars.
        global epsilon
        max_score, score, done = 0, 0, False

        # Reset and render the environment.
        current_state = env.reset()
        render_frame()

        for _ in range(steps_per_action):
            current_state, _, _, _ = env.step(1)
            render_frame()

        current_state = atari_preprocess(current_state, downsample_scale)
        current_state = np.stack((current_state, current_state, current_state), axis=2)
        current_state = np.reshape([current_state],
                                   (1, pixel_rows // downsample_scale, pixel_columns // downsample_scale,
                                    action_space_size))

        while not done:
            action = e_greedy_policy_action(epsilon, model, episode, total_observe_count, current_state,
                                            action_space_size)

            if epsilon > final_epsilon and episode > total_observe_count:
                epsilon -= epsilon_decay

            next_state, reward, done, _ = env.step(action)
            render_frame()

            next_state = atari_preprocess(next_state, downsample_scale)
            next_state = np.append(next_state, current_state[:, :, :, :], axis=3)

            replay_memory.append((current_state, action, reward, next_state))

            if episode > total_observe_count:
                agent.fit()

                if episode % target_model_change == 0:
                    target_model.set_weights(model.get_weights())

            score += reward
            current_state = next_state

            if max_score < score:
                print("max score for the episode {} is : {} ".format(episode, score))
                max_score = score

        if episode % 100 == 0:
            print("final score for the episode {} is : {} ".format(episode + 1, score))
            model.save("{}_{}.h5".format(filename_prefix, episode + 1))


if __name__ == '__main__':
    # Create the default parameters.
    filename_prefix = 'out/atari_skiing'
    render = True
    downsample_scale = 2
    steps_per_action = 3
    nEpisodes = 1
    epsilon = 1.
    total_observe_count = 750
    batch_size = 32
    gamma = .99
    final_epsilon = .1
    epsilon_decay = 1e-4
    target_model_change = 100
    replay_memory_size = 400000

    # Create the path to the file, if necessary.
    create_path(filename_prefix)

    # Create the skiing environment.
    env, state, pixel_rows, pixel_columns, action_space_size = create_skiing_environment()
    # Create the observation space's shape.
    observation_space_shape = (pixel_rows // downsample_scale, pixel_columns // downsample_scale, steps_per_action)

    # Create the replay memory for the agent.
    replay_memory = deque(maxlen=replay_memory_size)

    # Create the optimizer.
    optimizer = RMSprop(lr=0.00025, rho=0.95, epsilon=0.01)
    # Create the model and the target model.
    model = atari_skiing_model(observation_space_shape, action_space_size, optimizer)
    target_model = atari_skiing_model(observation_space_shape, action_space_size, optimizer)

    # Create the agent.
    agent = DQN(model, target_model, replay_memory, gamma, batch_size, observation_space_shape, action_space_size)

    # Start the game loop.
    game_loop()
