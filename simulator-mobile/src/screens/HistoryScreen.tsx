import React from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  Alert,
} from "react-native";
import { colors, spacing, radius } from "../constants/theme";
import { useSettings } from "../context/SettingsContext";
import { SimulationHistoryItem } from "../types/simulator";

export const HistoryScreen: React.FC = () => {
  const { history, clearHistory } = useSettings();

  const handleConfirmClear = () => {
    Alert.alert(
      "Clear History",
      "Are you sure you want to clear all simulation history logs?",
      [
        { text: "Cancel", style: "cancel" },
        { text: "Clear", style: "destructive", onPress: clearHistory },
      ]
    );
  };

  const renderItem = ({ item }: { item: SimulationHistoryItem }) => {
    return (
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Text style={styles.scenarioName}>{item.scenarioName}</Text>
          <View style={styles.statusBadge}>
            <Text style={styles.statusText}>{item.status}</Text>
          </View>
        </View>

        <View style={styles.metricsRow}>
          <View style={styles.metricItem}>
            <Text style={styles.metricLabel}>Generated</Text>
            <Text style={styles.metricValue}>{item.totalGenerated}</Text>
          </View>
          <View style={styles.metricItem}>
            <Text style={styles.metricLabel}>Accepted</Text>
            <Text style={styles.metricValue}>{item.totalAccepted}</Text>
          </View>
          <View style={styles.metricItem}>
            <Text style={styles.metricLabel}>Dispatched</Text>
            <Text style={[styles.metricValue, { color: colors.primary }]}>
              {item.notificationsDispatched}
            </Text>
          </View>
          <View style={styles.metricItem}>
            <Text style={styles.metricLabel}>Reduction</Text>
            <Text style={[styles.metricValue, { color: colors.success }]}>
              {item.reductionPercentage.toFixed(1)}%
            </Text>
          </View>
        </View>

        <View style={styles.footerRow}>
          <Text style={styles.rootCauseText} numberOfLines={1}>
            Cause: {item.probableRootCause}
          </Text>
          <Text style={styles.timeText}>
            {new Date(item.completedAt).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </Text>
        </View>
      </View>
    );
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Simulation History</Text>
          <Text style={styles.subtitle}>Audit log of executed alert scenarios</Text>
        </View>

        {history.length > 0 && (
          <TouchableOpacity
            style={styles.clearButton}
            onPress={handleConfirmClear}
            activeOpacity={0.7}
          >
            <Text style={styles.clearButtonText}>Clear Log</Text>
          </TouchableOpacity>
        )}
      </View>

      {history.length === 0 ? (
        <View style={styles.emptyContainer}>
          <Text style={styles.emptyTitle}>No Simulation History</Text>
          <Text style={styles.emptySubtitle}>
            Run an alert scenario from the Simulator tab to populate the audit log with real telemetry results.
          </Text>
        </View>
      ) : (
        <FlatList
          data={history}
          keyExtractor={(item) => item.id}
          renderItem={renderItem}
          contentContainerStyle={styles.listContent}
        />
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.md,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  title: {
    fontSize: 16,
    fontWeight: "800",
    color: colors.text,
  },
  subtitle: {
    fontSize: 11,
    color: colors.textSecondary,
    marginTop: 2,
  },
  clearButton: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm + 2,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceSubtle,
    borderWidth: 1,
    borderColor: colors.border,
  },
  clearButtonText: {
    fontSize: 11,
    fontWeight: "600",
    color: colors.critical,
  },
  listContent: {
    padding: spacing.md,
    paddingBottom: spacing.xxl * 2,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  scenarioName: {
    fontSize: 14,
    fontWeight: "700",
    color: colors.text,
    flex: 1,
  },
  statusBadge: {
    backgroundColor: colors.successLight,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.successBorder,
  },
  statusText: {
    fontSize: 10,
    fontWeight: "700",
    color: colors.success,
  },
  metricsRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radius.sm,
    padding: spacing.sm,
    marginBottom: spacing.xs,
  },
  metricItem: {
    alignItems: "center",
  },
  metricLabel: {
    fontSize: 9,
    fontWeight: "700",
    color: colors.textSecondary,
    textTransform: "uppercase",
    marginBottom: 2,
  },
  metricValue: {
    fontSize: 13,
    fontWeight: "800",
    color: colors.text,
  },
  footerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: spacing.xs,
  },
  rootCauseText: {
    fontSize: 11,
    color: colors.textSecondary,
    flex: 1,
  },
  timeText: {
    fontSize: 10,
    color: colors.textMuted,
    marginLeft: spacing.sm,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.xxl,
  },
  emptyTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: colors.text,
    marginBottom: 4,
  },
  emptySubtitle: {
    fontSize: 12,
    color: colors.textSecondary,
    textAlign: "center",
    lineHeight: 17,
  },
});
