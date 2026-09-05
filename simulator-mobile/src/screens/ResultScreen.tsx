import React from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Linking,
} from "react-native";
import { colors, spacing, radius } from "../constants/theme";
import { SimulationResult } from "../types/simulator";
import { useSettings } from "../context/SettingsContext";

interface ResultScreenProps {
  route?: {
    params?: {
      result: SimulationResult;
      scenarioName: string;
    };
  };
  navigation?: any;
}

export const ResultScreen: React.FC<ResultScreenProps> = ({ route, navigation }) => {
  const { result, scenarioName } = route?.params || ({} as any);
  const { dashboardUrl } = useSettings();

  const handleOpenDashboard = () => {
    Linking.openURL(dashboardUrl).catch(() => {
      // Fallback
      alert(`Could not open browser. Please navigate to ${dashboardUrl}`);
    });
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Header Badge */}
      <View style={styles.headerCard}>
        <View style={styles.badgeSuccess}>
          <Text style={styles.badgeText}>SIMULATION COMPLETED</Text>
        </View>
        <Text style={styles.title}>{result.scenario || scenarioName}</Text>
        <Text style={styles.timestampText}>
          Completed at: {new Date(result.timestamp || Date.now()).toLocaleTimeString()}
        </Text>
      </View>

      {/* Hero Reduction Banner */}
      <View style={styles.reductionCard}>
        <Text style={styles.reductionLabel}>Alert Fatigue Reduction</Text>
        <Text style={styles.reductionValue}>{result.reduction_percentage.toFixed(1)}%</Text>
        <Text style={styles.reductionSub}>
          {result.suppressed_count} noisy alerts filtered • {result.notifications_dispatched} actionable notifications dispatched
        </Text>
      </View>

      {/* Breakdown Grid */}
      <Text style={styles.sectionHeader}>Telemetry Processing Breakdown</Text>
      <View style={styles.grid}>
        <View style={styles.statBox}>
          <Text style={styles.statLabel}>Raw Alerts</Text>
          <Text style={styles.statNumber}>{result.total_generated}</Text>
        </View>

        <View style={styles.statBox}>
          <Text style={styles.statLabel}>Unique Signatures</Text>
          <Text style={styles.statNumber}>{result.unique_alerts}</Text>
        </View>

        <View style={styles.statBox}>
          <Text style={styles.statLabel}>Merged Duplicates</Text>
          <Text style={[styles.statNumber, { color: colors.primary }]}>
            {result.duplicates_merged}
          </Text>
        </View>

        <View style={styles.statBox}>
          <Text style={styles.statLabel}>Correlated</Text>
          <Text style={styles.statNumber}>{result.correlated_alerts}</Text>
        </View>

        <View style={styles.statBox}>
          <Text style={styles.statLabel}>Batched</Text>
          <Text style={styles.statNumber}>{result.batched_alerts}</Text>
        </View>

        <View style={styles.statBox}>
          <Text style={styles.statLabel}>Notifications Sent</Text>
          <Text style={[styles.statNumber, { color: colors.success }]}>
            {result.notifications_dispatched}
          </Text>
        </View>
      </View>

      {/* Probable Root Cause Card */}
      <View style={styles.rootCauseCard}>
        <View style={styles.rootCauseHeader}>
          <Text style={styles.rootCauseBadge}>PROBABLE ROOT CAUSE</Text>
          <Text style={styles.confidenceText}>Confidence: {result.confidence_score}%</Text>
        </View>
        <Text style={styles.rootCauseTitle}>{result.probable_root_cause}</Text>
        <Text style={styles.rootCauseDesc}>
          Topological BFS and temporal clustering identified this component as the chronological origin of cascading downstream failures.
        </Text>
      </View>

      {/* Notification Channel Dispatch */}
      <View style={styles.channelCard}>
        <Text style={styles.channelTitle}>Dispatched Notification Channels</Text>
        <View style={styles.channelRow}>
          <View style={styles.channelItem}>
            <Text style={styles.channelName}>PagerDuty (P1)</Text>
            <Text style={styles.channelCount}>
              {result.channel_breakdown?.pagerduty || 0}
            </Text>
          </View>
          <View style={styles.channelItem}>
            <Text style={styles.channelName}>Slack</Text>
            <Text style={styles.channelCount}>
              {result.channel_breakdown?.slack || 0}
            </Text>
          </View>
          <View style={styles.channelItem}>
            <Text style={styles.channelName}>Email</Text>
            <Text style={styles.channelCount}>
              {result.channel_breakdown?.email || 0}
            </Text>
          </View>
        </View>
      </View>

      {/* Action Buttons */}
      <View style={styles.actionsContainer}>
        <TouchableOpacity
          style={styles.dashboardButton}
          onPress={handleOpenDashboard}
          activeOpacity={0.8}
        >
          <Text style={styles.dashboardButtonText}>VIEW WEB DASHBOARD</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.backButton}
          onPress={() => navigation.navigate("Simulator")}
          activeOpacity={0.7}
        >
          <Text style={styles.backButtonText}>Run Another Simulation</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.md,
    paddingBottom: spacing.xxl * 2,
  },
  headerCard: {
    backgroundColor: colors.surface,
    padding: spacing.lg,
    borderRadius: radius.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  badgeSuccess: {
    alignSelf: "flex-start",
    backgroundColor: colors.successLight,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radius.sm,
    marginBottom: spacing.xs,
    borderWidth: 1,
    borderColor: colors.successBorder,
  },
  badgeText: {
    fontSize: 10,
    fontWeight: "700",
    color: colors.success,
  },
  title: {
    fontSize: 18,
    fontWeight: "800",
    color: colors.text,
    letterSpacing: -0.3,
  },
  timestampText: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: 2,
  },
  reductionCard: {
    backgroundColor: colors.surface,
    padding: spacing.lg,
    borderRadius: radius.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
  },
  reductionLabel: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.textSecondary,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  reductionValue: {
    fontSize: 38,
    fontWeight: "900",
    color: colors.success,
    letterSpacing: -1,
    marginVertical: spacing.xs,
  },
  reductionSub: {
    fontSize: 11,
    color: colors.textSecondary,
    textAlign: "center",
  },
  sectionHeader: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.textSecondary,
    textTransform: "uppercase",
    letterSpacing: 0.4,
    marginBottom: spacing.sm,
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginHorizontal: -4,
    marginBottom: spacing.md,
  },
  statBox: {
    width: "31%",
    backgroundColor: colors.surface,
    padding: spacing.sm,
    margin: "1%",
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
  },
  statLabel: {
    fontSize: 9,
    fontWeight: "700",
    color: colors.textSecondary,
    textAlign: "center",
    marginBottom: 2,
  },
  statNumber: {
    fontSize: 16,
    fontWeight: "800",
    color: colors.text,
  },
  rootCauseCard: {
    padding: spacing.md,
    borderRadius: radius.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.criticalBorder,
    backgroundColor: colors.criticalLight,
  },
  rootCauseHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 4,
  },
  rootCauseBadge: {
    fontSize: 10,
    fontWeight: "800",
    color: colors.critical,
    letterSpacing: 0.3,
  },
  confidenceText: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.critical,
  },
  rootCauseTitle: {
    fontSize: 15,
    fontWeight: "800",
    color: colors.text,
    marginBottom: 4,
  },
  rootCauseDesc: {
    fontSize: 11,
    color: colors.textSecondary,
    lineHeight: 15,
  },
  channelCard: {
    backgroundColor: colors.surface,
    padding: spacing.md,
    borderRadius: radius.md,
    marginBottom: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  channelTitle: {
    fontSize: 12,
    fontWeight: "700",
    color: colors.text,
    marginBottom: spacing.sm,
  },
  channelRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  channelItem: {
    flex: 1,
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radius.sm,
    padding: spacing.sm,
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.border,
  },
  channelName: {
    fontSize: 10,
    fontWeight: "600",
    color: colors.textSecondary,
    marginBottom: 2,
  },
  channelCount: {
    fontSize: 14,
    fontWeight: "800",
    color: colors.text,
  },
  actionsContainer: {
    gap: spacing.sm,
  },
  dashboardButton: {
    backgroundColor: colors.primary,
    borderRadius: radius.sm,
    paddingVertical: spacing.md,
    alignItems: "center",
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 2,
  },
  dashboardButtonText: {
    color: "#ffffff",
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 0.5,
  },
  backButton: {
    backgroundColor: colors.surface,
    borderRadius: radius.sm,
    paddingVertical: spacing.md,
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.border,
  },
  backButtonText: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "600",
  },
});
