import networkx as nx

from app.schemas.hr import ONAEdgeInput, ONAResponse


def run_ona(edges: list[ONAEdgeInput]) -> ONAResponse:
    graph = nx.Graph()
    for edge in edges:
        graph.add_edge(
            edge.source_employee_id,
            edge.target_employee_id,
            weight=edge.interaction_count,
        )

    if graph.number_of_nodes() == 0:
        return ONAResponse(
            most_central_employee_ids=[],
            most_isolated_employee_ids=[],
            average_degree=0,
        )

    centrality = nx.degree_centrality(graph)
    avg_degree = sum(dict(graph.degree()).values()) / graph.number_of_nodes()

    sorted_central = sorted(centrality.items(), key=lambda kv: kv[1], reverse=True)
    sorted_isolated = sorted(centrality.items(), key=lambda kv: kv[1])

    return ONAResponse(
        most_central_employee_ids=[employee_id for employee_id, _ in sorted_central[:3]],
        most_isolated_employee_ids=[employee_id for employee_id, _ in sorted_isolated[:3]],
        average_degree=round(avg_degree, 2),
    )
