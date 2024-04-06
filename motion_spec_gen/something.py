import uuid
import rdflib
from rdflib.collection import Collection
from motion_spec_gen.namespaces import (
    Controller,
    PIDController,
    THRESHOLD,
    CONSTRAINT,
    GEOM_COORD,
    ACHD_SOLVER,
    EMBED_MAP,
)

vector_components = {
    "X": (1, 0, 0),
    "Y": (0, 1, 0),
    "Z": (0, 0, 1),
    "XY": (1, 1, 0),
    "XZ": (1, 0, 1),
    "YZ": (0, 1, 1),
    "XYZ": (1, 1, 1),
}


linear_vector_type_to_num = {
    **{
        getattr(GEOM_COORD, f"LinearVelocityVector{suffix}"): vector
        for suffix, vector in vector_components.items()
    }
}

angular_vector_type_to_num = {
    **{
        getattr(GEOM_COORD, f"AngularVelocityVector{suffix}"): vector
        for suffix, vector in vector_components.items()
    }
}


class PIDControllerStep:

    def emit(self, g: rdflib.Graph, node: rdflib.URIRef, **kwargs) -> dict:
        """
        Add an output node to the graph for pid controller
        """

        constraint = g.value(node, Controller.constraint)

        # *Assumption: compute using setpoint
        coordinate = g.value(constraint, CONSTRAINT.quantity)

        output_data = {}

        qname = g.compute_qname(node)
        prefix = qname[1]
        name = qname[2]

        # get solver from embed map
        embed_map = g.value(predicate=EMBED_MAP.controller, object=node)
        solver = g.value(embed_map, EMBED_MAP.solver)
        solver_name = g.compute_qname(solver)[2]

        # TOOD: check for a better way
        is_geom_coord = (
            g[coordinate : rdflib.RDF.type : GEOM_COORD.PositionCoordinate]
            or g[coordinate : rdflib.RDF.type : GEOM_COORD.DistanceCoordinate]
            or g[coordinate : rdflib.RDF.type : GEOM_COORD.VelocityTwistCoordinate]
            or g[coordinate : rdflib.RDF.type : GEOM_COORD.AccelerationTwistCoordinate]
        )

        # *Assumption: one controller signal can be mapped to only one type of output
        if is_geom_coord:
            # type = AccelerationEnergy
            output_data["output"] = {
                "type": "output-acceleration-energy",
                "var_name": rdflib.URIRef(f"{prefix}{solver_name}_output_acceleration_energy"),
            }

            g.add(
                (
                    solver,
                    ACHD_SOLVER["acceleration-energy"],
                    output_data["output"]["var_name"],
                )
            )

        else:
            # type = ExternalWrench
            output_data["output"] = {
                "type": "output-external-wrench",
                "var_name": rdflib.URIRef(f"{prefix}{solver_name}_output_external_wrench"),
            }

            g.add(
                (
                    solver,
                    ACHD_SOLVER["external-wrench"],
                    (output_data["output"]["var_name"]),
                )
            )

        
        types_of_coord = list(g.objects(coordinate, rdflib.RDF.type))
        # get the type with "vector" in it
        vec_type = [t for t in types_of_coord if "vector" in str(t).lower()][0]
        vec_type_qname = g.compute_qname(vec_type)[2]

        output_data["vector"] = [0, 0, 0, 0, 0, 0]
        if "linear" in vec_type_qname.lower():
            output_data["vector"][0:3] = linear_vector_type_to_num[vec_type]

        elif "angular" in vec_type_qname.lower():
            output_data["vector"][3:] = angular_vector_type_to_num[vec_type]
                
        signal = rdflib.URIRef(f"{prefix}{name}_signal")
        # add the signal to the controller
        g.add((node, Controller.signal, rdflib.URIRef(signal)))

        # add the output node to the graph
        # add vector as a collection
        vector_collection = rdflib.BNode()
        l = [rdflib.Literal(i) for i in output_data["vector"]]
        Collection(g, vector_collection, l)
        g.add((embed_map, EMBED_MAP.vector, vector_collection))
        # add input
        g.add((embed_map, EMBED_MAP.input, signal))
        # add the output data
        g.add(
            (
                embed_map,
                EMBED_MAP[output_data["output"]["type"]],
                output_data["output"]["var_name"],
            )
        )

        print(output_data)
