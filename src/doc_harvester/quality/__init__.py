"""Built-in provider-neutral quality evaluation."""

from doc_harvester.quality.basic import BasicQualityGate
from doc_harvester.quality.factory import available_quality_gates, create_quality_gate

__all__ = ["BasicQualityGate", "available_quality_gates", "create_quality_gate"]
