import React from "react";
import { TopologyData } from "../../types";
import { ServiceTopologyView } from "../Topology/ServiceTopologyView";

interface RootCauseGraphProps {
  topology: TopologyData;
  onRefreshTopology?: () => void;
}

export const RootCauseGraph: React.FC<RootCauseGraphProps> = ({
  topology,
  onRefreshTopology = () => {},
}) => {
  return (
    <ServiceTopologyView
      topology={topology}
      onRefreshTopology={onRefreshTopology}
      initialViewMode="graph"
    />
  );
};
