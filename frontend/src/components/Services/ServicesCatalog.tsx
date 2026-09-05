import React from "react";
import { TopologyData } from "../../types";
import { ServiceTopologyView } from "../Topology/ServiceTopologyView";

interface ServicesCatalogProps {
  topology: TopologyData;
  onRefreshTopology?: () => void;
}

export const ServicesCatalog: React.FC<ServicesCatalogProps> = ({
  topology,
  onRefreshTopology = () => {},
}) => {
  return (
    <ServiceTopologyView
      topology={topology}
      onRefreshTopology={onRefreshTopology}
      initialViewMode="catalog"
    />
  );
};
