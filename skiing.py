from os import path
from warnings import warn

from core.agent import DQN, load_dqn_agent
from core.model import atari_skiing_model, huber_loss, frame_can_pass_the_net, MIN_FRAME_DIM_THAT_PASSES_NET, \
    initialize_optimizer
from core.policy import EGreedyPolicy
from game_engine.game import Game, GameResultSpecs
from utils.parser import create_parser
from utils.system_operations import create_path


def run_checks() -> None:
    """ Checks the input arguments. """
    # Set default variables.
    poor_observe = bad_target_model_change = 500
    frame_history_ceiling = 10

    # Create the path to the files, if necessary.
    create_path(agent_name_prefix)
    create_path(plots_name_prefix)
    create_path(results_name_prefix)

    if info_interval_mean == 1:
        warn('Info interval mean has no point to be 1. '
             'The program will continue, but the means will be ignored.'.format(info_interval_mean))

    if target_model_change < bad_target_model_change:
        warn('Target model change is extremely small ({}). This will possibly make the agent unstable.'
             'Consider a value greater than {}'.format(target_model_change, bad_target_model_change))

    if not path.exists(agent_path) and agent_path != '':
        raise FileNotFoundError('File {} not found.'.format(agent_path))

    if agent_frame_history > frame_history_ceiling:
        warn('The agent\'s frame history is too big ({}). This will possibly make the agent unstable and slower.'
             'Consider a value smaller than {}'.format(agent_frame_history, frame_history_ceiling))

    if downsample_scale == 1:
        warn('Downsample scale set to 1. This means that the atari frames will not be scaled down.')

    # Downsampling should result with at least 32 pixels on each dimension,
    # because the first convolutional layer has a filter 8x8 with stride 4x4.
    if not frame_can_pass_the_net(game.observation_space_shape[1], game.observation_space_shape[2]):
        raise ValueError('Downsample is too big. It can be set from 1 to {}'
                         .format(min(int(game.pixel_rows / MIN_FRAME_DIM_THAT_PASSES_NET),
                                     int(game.pixel_columns / MIN_FRAME_DIM_THAT_PASSES_NET))))

    if plot_train_results and episodes == 1:
        warn('Cannot plot for 1 episode only.')

    if epsilon > 1:
        raise ValueError('Epsilon cannot be set to a greater value than 1.'
                         'Got {}'.format(epsilon))

    if final_epsilon > 1:
        raise ValueError('Epsilon cannot be set to a greater value than 1.'
                         'Got {}'.format(final_epsilon))

    if final_epsilon > epsilon:
        raise ValueError('Final epsilon ({}) cannot be greater than epsilon ({}).'
                         .format(final_epsilon, epsilon))

    if (epsilon_decay > epsilon - final_epsilon) and epsilon != final_epsilon:
        warn('Epsilon decay ({}) is too big, compared with epsilon ({}) and final epsilon ({})!'
             .format(epsilon_decay, epsilon, final_epsilon))

    if total_observe_count < poor_observe and agent_path == '':
        warn('The total number of observing steps ({}) is too small and could bring poor results.'
             'Consider a value grater than {}'.format(total_observe_count, poor_observe))

    final_memory_size = agent.memory.end + total_observe_count
    if final_memory_size < batch_size:
        raise ValueError('The total number of observing steps ({}) '
                         'cannot be smaller than the agent\'s memory size ( current = {}, final = {} )'
                         ' after the observing steps ({}).'
                         .format(total_observe_count, agent.memory.end, final_memory_size,
                                 total_observe_count))


class IncompatibleAgentConfigurationError(Exception):
    pass


def create_agent() -> DQN:
    """
    Creates the atari skiing agent.

    :return: the agent.
    """
    if agent_path != '':
        # Load the agent.
        dqn = load_dqn_agent(agent_path, {'huber_loss': huber_loss})

        # Check for agent configuration conflicts.
        if dqn.observation_space_shape != game.observation_space_shape:
            raise IncompatibleAgentConfigurationError('Incompatible observation space shapes have been encountered.'
                                                      'The loaded agent has shape {}, '
                                                      'but the new requested shape is {}.'
                                                      .format(dqn.observation_space_shape,
                                                              game.observation_space_shape))

        if dqn.action_size != game.action_space_size:
            raise IncompatibleAgentConfigurationError('')

        # Use the new configuration parameters.
        dqn.target_model_change = target_model_change
        dqn.gamma = gamma
        dqn.batch_size = batch_size
        dqn.policy = policy
        print('Agent {} has been loaded successfully.'.format(agent_path))
    else:
        # Init the model.
        model = atari_skiing_model(game.observation_space_shape, game.action_space_size, optimizer)
        # Create the agent.
        dqn = DQN(model, target_model_change, gamma, batch_size, game.observation_space_shape,
                  game.action_space_size, policy, memory_size=replay_memory_size)

    return dqn


if __name__ == '__main__':
    # Get arguments.
    args = create_parser().parse_args()
    agent_name_prefix = args.filename_prefix
    results_name_prefix = args.results_name_prefix
    recording_name_prefix = args.recording_name_prefix
    results_save_interval = args.results_save_interval
    agent_save_interval = args.save_interval
    info_interval_current = args.info_interval_current
    info_interval_mean = args.info_interval_mean
    target_model_change = args.target_interval
    agent_path = args.agent
    agent_frame_history = args.agent_history
    plot_train_results = not args.no_plot
    save_plots = not args.no_save_plots
    plots_name_prefix = args.plot_name
    render = not args.no_render
    record = args.record
    downsample_scale = args.downsample
    steps_per_action = args.frame_skipping
    fit_frequency = args.fit_frequency
    no_operation = args.no_operation
    episodes = args.episodes
    epsilon = args.epsilon
    final_epsilon = args.final_epsilon
    epsilon_decay = args.decay
    total_observe_count = args.observe
    replay_memory_size = args.replay_memory
    batch_size = args.batch
    gamma = args.gamma
    optimizer_name = args.optimizer
    learning_rate = args.learning_rate
    lr_decay = args.learning_rate_decay
    beta1 = args.beta1
    beta2 = args.beta2
    rho = args.rho
    fuzz = args.fuzz
    momentum = args.momentum

    # Create the game specs.
    game_specs = GameResultSpecs(info_interval_current, info_interval_mean, agent_save_interval, results_save_interval,
                                 plots_name_prefix, results_name_prefix, agent_name_prefix, recording_name_prefix,
                                 plot_train_results, save_plots)

    # Create the game.
    game = Game(episodes, downsample_scale, agent_frame_history, steps_per_action, fit_frequency,
                no_operation, game_specs, render, record)

    # Create the optimizer.
    optimizer = initialize_optimizer(optimizer_name, learning_rate, beta1, beta2, lr_decay, rho, fuzz, momentum)

    # Create the policy.
    policy = EGreedyPolicy(epsilon, final_epsilon, epsilon_decay, total_observe_count, game.action_space_size)

    # Create the agent.
    agent = create_agent()

    # Check arguments.
    run_checks()

    # Play the game, using the agent.
    game.play_game(agent)
