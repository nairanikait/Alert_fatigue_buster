import React, { useState, useEffect, useRef } from "react";
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
  Alert,
} from "react-native";
import { colors, spacing, radius } from "../constants/theme";
import { createApiClient } from "../api/client";
import { useSettings } from "../context/SettingsContext";
import { SimulationResult, SimulationHistoryItem, ScenarioId } from "../types/simulator";

interface ProgressScreenProps {
  route?: any;
  navigation?: any;
}

export const ProgressScreen: React.FC<ProgressScreenProps> = ({ route, navigation }) => {
  const { scenarioId, scenarioName, totalCount = 500, params } = route?.params || {};
  const { backendUrl, addHistoryItem } = useSettings();

  const [progressPercent, setProgressPercent] = useState<number>(10);
  const [eventsSent, setEventsSent] = useState<number>(0);
  const [backendAccepted, setBackendAccepted] = useState<number>(0);
  const [statusMessage, setStatusMessage] = useState<string>("Initializing alert stream...");
  const [error, setError] = useState<string | null>(null);

  const isCancelledRef = useRef<boolean>(false);

  useEffect(() => {
    runExecution();
    return () => {
      isCancelledRef.current = true;
    };
  }, []);

  const runExecution = async () => {
    isCancelledRef.current = false;
    setError(null);
    const startTime = new Date().toISOString();

    const client = createApiClient(backendUrl);

    // Animate progress indicators while backend processes
    const interval = setInterval(() => {
      if (isCancelledRef.current) {
        clearInterval(interval);
        return;
      }
      setProgressPercent((prev) => {
        if (prev >= 90) return prev;
        return prev + 15;
      });
      setEventsSent((prev) => Math.min(totalCount, prev + Math.ceil(totalCount / 6)));
      setBackendAccepted((prev) => Math.min(totalCount, prev + Math.ceil(totalCount / 7)));
    }, 250);

    try {
      setStatusMessage("Dispatching alerts to pipeline...");
      let res: SimulationResult;

      switch (scenarioId) {
        case "database_outage":
          res = await client.runDatabaseOutage();
          break;
        case "flaky_pod":
          res = await client.runFlakyPod();
          break;
        case "alert_storm":
          res = await client.runAlertStorm(params);
          break;
        case "critical_emergency":
          res = await client.runCriticalEmergency();
          break;
        case "service_cascade":
          res = await client.runServiceCascade();
          break;
        case "recovery":
          res = await client.runRecovery();
          break;
        default:
          res = await client.runScenario(scenarioId, params);
      }

      clearInterval(interval);

      if (isCancelledRef.current) return;

      setProgressPercent(100);
      setEventsSent(res.total_generated);
      setBackendAccepted(res.total_accepted);
      setStatusMessage("Simulation processed successfully!");

      // Save to History
      const historyItem: SimulationHistoryItem = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        scenarioId,
        scenarioName: res.scenario || scenarioName,
        status: "Completed",
        totalGenerated: res.total_generated,
        totalAccepted: res.total_accepted,
        suppressedCount: res.suppressed_count,
        notificationsDispatched: res.notifications_dispatched,
        reductionPercentage: res.reduction_percentage,
        probableRootCause: res.probable_root_cause,
        startedAt: startTime,
        completedAt: new Date().toISOString(),
      };
      await addHistoryItem(historyItem);

      // Transition to Result Screen
      setTimeout(() => {
        if (!isCancelledRef.current) {
          navigation.replace("Result", { result: res, scenarioName });
        }
      }, 400);
    } catch (err: any) {
      clearInterval(interval);
      if (isCancelledRef.current) return;

      const msg = err.response?.data?.detail || err.message || "Failed to communicate with backend";
      setError(msg);
      setStatusMessage("Simulation failed");
    }
  };

  const handleStop = () => {
    isCancelledRef.current = true;
    navigation.goBack();
  };

  return (
    <View style={styles.container}>
      <View style={styles.card}>
        <Text style={styles.badgeText}>SIMULATION IN PROGRESS</Text>
        <Text style={styles.title}>{scenarioName}</Text>
        <Text style={styles.statusText}>{statusMessage}</Text>

        {error ? (
          <View style={styles.errorBox}>
            <Text style={styles.errorTitle}>Simulation Execution Error</Text>
            <Text style={styles.errorMessage}>{error}</Text>
            <View style={styles.errorActions}>
              <TouchableOpacity style={styles.retryButton} onPress={runExecution}>
                <Text style={styles.retryText}>Retry</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.backButton} onPress={() => navigation.goBack()}>
                <Text style={styles.backText}>Go Back</Text>
              </TouchableOpacity>
            </View>
          </View>
        ) : (
          <>
            {/* Progress Bar */}
            <View style={styles.progressTrack}>
              <View style={[styles.progressFill, { width: `${progressPercent}%` }]} />
            </View>

            <View style={styles.statsGrid}>
              <View style={styles.statBox}>
                <Text style={styles.statLabel}>Target Volume</Text>
                <Text style={styles.statValue}>{totalCount}</Text>
              </View>

              <View style={styles.statBox}>
                <Text style={styles.statLabel}>Events Sent</Text>
                <Text style={[styles.statValue, { color: colors.primary }]}>{eventsSent}</Text>
              </View>

              <View style={styles.statBox}>
                <Text style={styles.statLabel}>Backend Accepted</Text>
                <Text style={[styles.statValue, { color: colors.success }]}>
                  {backendAccepted}
                </Text>
              </View>
            </View>

            <View style={styles.loadingRow}>
              <ActivityIndicator size="small" color={colors.primary} />
              <Text style={styles.loadingText}>
                Correlating topology, deduplicating bursts & evaluating cooldowns...
              </Text>
            </View>

            {/* Stop Simulation Button */}
            <TouchableOpacity style={styles.stopButton} onPress={handleStop} activeOpacity={0.7}>
              <Text style={styles.stopButtonText}>Stop / Cancel Simulation</Text>
            </TouchableOpacity>
          </>
        )}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: "center",
    padding: spacing.lg,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.xl,
    borderWidth: 1,
    borderColor: colors.border,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 4,
    elevation: 2,
  },
  badgeText: {
    fontSize: 10,
    fontWeight: "800",
    color: colors.primary,
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  title: {
    fontSize: 18,
    fontWeight: "800",
    color: colors.text,
    letterSpacing: -0.3,
    marginBottom: 4,
  },
  statusText: {
    fontSize: 12,
    color: colors.textSecondary,
    marginBottom: spacing.lg,
  },
  progressTrack: {
    height: 8,
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radius.full,
    overflow: "hidden",
    marginBottom: spacing.lg,
  },
  progressFill: {
    height: "100%",
    backgroundColor: colors.primary,
    borderRadius: radius.full,
  },
  statsGrid: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: spacing.lg,
    gap: spacing.sm,
  },
  statBox: {
    flex: 1,
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radius.sm,
    padding: spacing.sm,
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.border,
  },
  statLabel: {
    fontSize: 9,
    fontWeight: "700",
    color: colors.textSecondary,
    textTransform: "uppercase",
    marginBottom: 2,
  },
  statValue: {
    fontSize: 15,
    fontWeight: "800",
    color: colors.text,
  },
  loadingRow: {
    flexDirection: "row",
    alignItems: "center",
    marginVertical: spacing.md,
    gap: spacing.sm,
  },
  loadingText: {
    fontSize: 11,
    color: colors.textSecondary,
    flex: 1,
    lineHeight: 15,
  },
  stopButton: {
    marginTop: spacing.md,
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radius.sm,
    paddingVertical: spacing.sm + 2,
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.border,
  },
  stopButtonText: {
    fontSize: 12,
    fontWeight: "600",
    color: colors.critical,
  },
  errorBox: {
    backgroundColor: colors.criticalLight,
    padding: spacing.md,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.criticalBorder,
    marginTop: spacing.sm,
  },
  errorTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: colors.critical,
    marginBottom: 4,
  },
  errorMessage: {
    fontSize: 12,
    color: colors.text,
    marginBottom: spacing.md,
  },
  errorActions: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  retryButton: {
    backgroundColor: colors.primary,
    paddingVertical: spacing.xs + 2,
    paddingHorizontal: spacing.md,
    borderRadius: radius.sm,
  },
  retryText: {
    color: "#ffffff",
    fontSize: 12,
    fontWeight: "700",
  },
  backButton: {
    backgroundColor: colors.surface,
    paddingVertical: spacing.xs + 2,
    paddingHorizontal: spacing.md,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  backText: {
    color: colors.text,
    fontSize: 12,
    fontWeight: "600",
  },
});
