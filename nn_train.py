import math
import random

import numpy
import torch
from torch import nn


class QNetwork(nn.Module):
    def __init__(self):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(8, 128),
            nn.Linear(128, 128),
            nn.Linear(128, 4),
        )

    def forward(self, x):
        return self.network(x)


if __name__ == "__main__":
    agent = QNetwork()
    target = QNetwork()
    agent.load_state_dict(torch.load("model_new"))
    target.load_state_dict(torch.load("model_new"))
    loss_fn = nn.SmoothL1Loss()
    optimizer = torch.optim.AdamW(agent.parameters(), lr=1e-4, amsgrad=True)

    from collections import deque
    import gymnasium as gym

    env = gym.make("LunarLander-v2")

    episodes = 10000

    memory_size = 10000
    observations = deque(maxlen=memory_size)
    actions = deque(maxlen=memory_size)
    rewards = deque(maxlen=memory_size)
    next_observations = deque(maxlen=memory_size)
    dones = deque(maxlen=memory_size)

    eps_start = 0.9
    eps_end = 0.05
    eps_decay = 1000
    eps = eps_start

    step = 0
    best_model = None

    last_rewards = deque(maxlen=100)
    best_last_rewards = float("-inf")
    for episode in range(episodes):
        episode_reward = 0.0
        observation, _ = env.reset()
        while True:
            observations.append(observation)
            eps_threshold = eps_end + (eps_start - eps_end) * math.exp(-1.0 * step / eps_decay)
            with torch.no_grad():
                if random.random() > eps_threshold:
                    action = agent(torch.Tensor(observation)).argmax(dim=0).item()
                else:
                    action = env.action_space.sample()
            actions.append(action)
            observation, reward, terminated, truncated, _ = env.step(action)
            rewards.append(reward)
            next_observations.append(observation)
            dones.append(int(terminated or truncated))

            batch_size = 128
            if len(observations) >= batch_size:
                batch_observations = []
                batch_actions = []
                batch_rewards = []
                batch_next_observations = []
                batch_dones = []
                n = len(observations)
                for _ in range(batch_size):
                    rnd = random.randrange(n)
                    batch_observations.append(observations[rnd])
                    batch_actions.append(actions[rnd])
                    batch_rewards.append(rewards[rnd])
                    batch_next_observations.append(next_observations[rnd])
                    batch_dones.append(dones[rnd])

                with torch.no_grad():
                    future_rewards = target(torch.Tensor(numpy.stack(batch_next_observations, axis=0)))
                    current_rewards = agent(torch.Tensor(numpy.stack(batch_observations, axis=0)))
                for i in range(batch_size):
                    current_rewards[i][batch_actions[i]] = batch_rewards[i] + 0.99 * future_rewards[i].max().item()

                pred = agent(torch.Tensor(numpy.stack(batch_observations, axis=0)))
                loss = loss_fn(pred, current_rewards)
                loss.backward()
                torch.nn.utils.clip_grad_value_(agent.parameters(), 100)
                optimizer.step()
                optimizer.zero_grad()

                target_state_dict = target.state_dict()
                agent_state_dict = agent.state_dict()
                for key in agent_state_dict:
                    target_state_dict[key] = agent_state_dict[key] * 0.005 + target_state_dict[key] * (1 - 0.005)
                target.load_state_dict(target_state_dict)

            episode_reward += reward

            step += 1
            if terminated or truncated:
                last_rewards.append(episode_reward)
                break
        avg = numpy.mean(last_rewards)
        if episode % 10 == 0:
            print(episode, avg)
        if avg >= best_last_rewards:
            best_last_rewards = avg
            best_model = agent.state_dict()
            torch.save(agent.state_dict(), "model_new")
    env.close()