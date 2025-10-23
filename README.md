# TheMCPCompany: Creating General-purpose Agents with Task-specific Tools [[ArXiv]](https://arxiv.org/abs/2510.19286)

> Since the introduction of the Model Context Protocol (MCP), the number of available tools for Large Language Models (LLMs) has increased significantly. These task-specific tool sets offer an alternative to general-purpose tools such as web browsers, while being easier to develop and maintain than GUIs. However, current general-purpose agents predominantly rely on web browsers for interacting with the environment. Here, we introduce TheMCPCompany, a benchmark for evaluating tool-calling agents on tasks that involve interacting with various real-world services. We use the REST APIs of these services to create MCP servers, which include over 18,000 tools. We also provide manually annotated ground-truth tools for each task. In our experiments, we use the ground truth tools to show the potential of tool-calling agents for both improving performance and reducing costs assuming perfect tool retrieval. Next, we explore agent performance using tool retrieval to study the real-world practicality of tool-based agents. While all models with tool retrieval perform similarly or better than browser-based agents, smaller models cannot take full advantage of the available tools through retrieval. On the other hand, GPT-5's performance with tool retrieval is very close to its performance with ground-truth tools. Overall, our work shows that the most advanced reasoning models are effective at discovering tools in simpler environments, but seriously struggle with navigating complex enterprise environments. TheMCPCompany reveals that navigating tens of thousands of tools and combining them in non-trivial ways to solve complex problems is still a challenging task for current models and requires both better reasoning and better retrieval models.

<br>

<p align="center"><img alt="TheMCPCompany" src="https://huggingface.co/datasets/BatsResearch/themcpcompany_artifacts/resolve/main/tmc.svg"/></p>

## Running the Agent

Follow these steps to run the agent:

- Set up the environment that the agent interacts with:
  - For TheAgentCompany tasks, follow the official instructions from [here](https://github.com/TheAgentCompany/TheAgentCompany) to run the docker containers.
  - For Azure tasks, follow [these instructions](./azure_tasks/README.md) to create an Azure account and a service principle.
- Run the MCP servers. Follow [these instructions](./mcp_servers/README.md) to run the MCP servers. _Not needed for the agent with the browser tool_.
- Follow [these instructions](./OpenHands/README.md) to set up OpenHands and run the evaluations.


## Citation

```bibtex
@misc{tmc,
      title={TheMCPCompany: Creating General-purpose Agents with Task-specific Tools}, 
      author={Reza Esfandiarpoor and Vishwas Suryanarayanan and Stephen H. Bach and Vishal Chowdhary and Anthony Aue},
      year={2025},
      eprint={2510.19286},
      archivePrefix={arXiv},
      primaryClass={cs.CL},
      url={https://arxiv.org/abs/2510.19286}, 
}
```
