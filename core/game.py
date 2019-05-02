from collections import Generator

import gym
import numpy as np
from gym.wrappers import TimeLimit
from math import inf, ceil

from core.agent import DQN
from utils.preprocessing import atari_preprocess
from utils.scoring import Scorer


class Game(object):
    def __init__(self, episodes: int, render: bool, downsample_scale: int, scorer: Scorer, agent_frame_history: int,
                 steps_per_action: int):
        self._episodes = episodes
        self._render = render
        self._downsample_scale = downsample_scale
        self._scorer = scorer
        self._agent_frame_history = agent_frame_history
        self._steps_per_action = steps_per_action

        # Create the skiing environment.
        self._env, self.pixel_rows, self.pixel_columns, self.action_space_size = self._create_skiing_environment()

        # Create the observation space's shape.
        self.observation_space_shape = (ceil(self.pixel_rows / self._downsample_scale),
                                        ceil(self.pixel_columns / self._downsample_scale),
                                        self._agent_frame_history)

    @staticmethod
    def _create_skiing_environment() -> [TimeLimit, int, int, int]:
        """
        Creates a skiing environment.

        :return: the skiing environment, the image's height, the image's width and the action space's size.
        """
        # Create the skiing environment.
        environment = gym.make('Skiing-v0')
        # Get the observation space's height and width.
        height, width = environment.observation_space.shape[0], environment.observation_space.shape[1]
        # Get the number of possible moves.
        act_space_size = environment.action_space.n

        return environment, height, width, act_space_size

    def _render_frame(self) -> None:
        """ Renders a frame, only if the user has chosen to do so. """
        if self._render:
            self._env.render()

    def _take_actions(self, agent: DQN, current_state: np.ndarray) -> [float, np.ndarray]:
        """
        Takes game actions.

        :param agent: the agent to take the actions.
        :param current_state: the current state.
        :return: the next state, the reward and if game is done.
        """
        # Init variables.
        reward, next_state, done = 0, current_state, False

        for _ in range(self._steps_per_action):
            # Take an action, using the policy.
            action = agent.take_action(current_state)
            # Take a step, using the action.
            next_state, reward, done, _ = self._env.step(action)

            if done:
                return next_state, reward, done

            # Render the frame.
            self._render_frame()

            # Preprocess the state.
            next_state = atari_preprocess(next_state, self._downsample_scale)
            # Append the frame history.
            next_state = np.append(next_state, current_state[:, :, :, :self._agent_frame_history - 1], axis=3)

            # Save sample <s,a,r,s'> to the replay memory.
            agent.append_to_memory(current_state, action, reward, next_state)

        return next_state, reward, done

    def play_game(self, agent: DQN) -> Generator:
        """
        Starts the game loop and trains the agent.

        :param agent: the agent to play the game.
        :return: generator containing the finished episode number.
        """
        # Run for a number of episodes.
        for episode in range(1, self._episodes + 1):
            # Init vars.
            max_score, total_score, done = -inf, 0, False

            # Reset and render the environment.
            current_state = self._env.reset()
            self._render_frame()

            # Preprocess current_state.
            current_state = atari_preprocess(current_state, self._downsample_scale)

            # Create preceding frames, using the starting frame.
            current_state = np.stack(tuple([current_state for _ in range(self._agent_frame_history)]), axis=2)

            # Set current state with the stacked.
            current_state = np.reshape(current_state,
                                       (1,
                                        ceil(self.pixel_rows / self._downsample_scale),
                                        ceil(self.pixel_columns / self._downsample_scale),
                                        self._agent_frame_history))

            while not done:
                next_state, reward, done = self._take_actions(agent, current_state)

                # Fit agent and keep fitting history.
                fitting_history = agent.fit()
                if fitting_history is not None:
                    self._scorer.huber_loss_history[episode - 1] += fitting_history.history['loss']

                # Add reward to the total score.
                total_score += reward
                # Set current state with the next.
                current_state = next_state
                # Set max score.
                max_score = max(max_score, reward)

            # Add scores to the scores arrays.
            self._scorer.max_scores[episode - 1] = max_score
            self._scorer.total_scores[episode - 1] = total_score

            # Yield the finished episode.
            yield episode
