import React, { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  Platform,
} from "react-native";
import { colors, spacing, radius } from "../constants/theme";
import { ScenarioMetadata, StormParams } from "../types/simulator";
import { ScenarioCard } from "../components/ScenarioCard";
import { ConfirmationModal } from "../components/ConfirmationModal";
import { useSettings } from "../context/SettingsContext";
import { createApiClient } from "../api/client";

interface SimulatorScreenProps {
  navigation: any;
}

const SCENARIOS: ScenarioMetadata[] = [
  {
    id: "database_outage",
    name: "1. Database Outage",
    tag: "Flagship Scenario • 500 Alerts",
    description: "Simulates a primary database connection crash at T=0 followed by 499 cascading downstream service failures across Payment, Orders, Auth, and API Gateway.",
    expectedBehavior: "500 raw alerts → deduplication merges repeated errors → correlation pins database root cause → only 1–2 actionable incident alerts dispatched.",
    defaultAlertCount: 500,
    severity: "critical",
    buttonText: "START DATABASE OUTAGE",
    badgeColor: colors.criticalLight,
    badgeTextColor: colors.critical,
  },
  {
    id: "flaky_pod",
    name: "2. Flaky Pod Flapping",
    tag: "Noise Quarantine • 64 Alerts",
    description: "Simulates a Kubernetes pod flapping rapidly between Firing (OOMKilled) and Resolved states to test lifecycle noise dampening.",
    expectedBehavior: "Rapid transitions detected by Flaky Detector → alert flagged as FLAKY with extended cooldown → pages suppressed.",
    defaultAlertCount: 64,
    severity: "medium",
    buttonText: "START FLAKY POD",
    badgeColor: colors.mediumLight,
    badgeTextColor: colors.medium,
  },
  {
    id: "alert_storm",
    name: "3. Alert Storm",
    tag: "High Volume Burst • 500+ Alerts",
    description: "Multi-service resource saturation spike (HighCPU, HighMemory, QueueBacklog, DiskPressure) testing deduplication throughput.",
    expectedBehavior: "Alerts collated in 10s sliding batch window → batched into structured digests → notification volume reduced by >95%.",
    defaultAlertCount: 500,
    severity: "high",
    buttonText: "START ALERT STORM",
    badgeColor: colors.purpleLight,
    badgeTextColor: colors.purple,
  },
  {
    id: "critical_emergency",
    name: "4. Critical Emergency",
    tag: "Never Silenced • P1 Solitary",
    description: "Generates a solitary P1 critical event (ProductionDatabaseDown) that must never be suppressed despite noise reduction policies.",
    expectedBehavior: "Critical emergency immediately bypasses batch delay & cooldowns → routed straight to PagerDuty.",
    defaultAlertCount: 1,
    severity: "critical",
    buttonText: "TRIGGER CRITICAL EMERGENCY",
    badgeColor: colors.criticalLight,
    badgeTextColor: colors.critical,
  },
  {
    id: "service_cascade",
    name: "5. Service Cascade",
    tag: "Topological Order • 280 Alerts",
    description: "Fires alerts in strict topological dependency order: Database → Payment → Orders → Checkout → API Gateway.",
    expectedBehavior: "Causal graph correlates temporal proximity and topology → flags Database as root cause, marking downstream as symptoms.",
    defaultAlertCount: 280,
    severity: "high",
    buttonText: "START SERVICE CASCADE",
    badgeColor: colors.primaryLight,
    badgeTextColor: colors.primary,
  },
  {
    id: "recovery",
    name: "6. Incident Auto-Recovery",
    tag: "Resolution Signal • Active Incidents",
    description: "Dispatches resolved signals for all active firing alerts to close open incidents and record MTTR duration.",
    expectedBehavior: "Alerts transition to RESOLVED → active incidents closed → dashboard counters decrease.",
    defaultAlertCount: 10,
    severity: "low",
    buttonText: "DISPATCH RECOVERY SIGNALS",
    badgeColor: colors.successLight,
    badgeTextColor: colors.success,
  },
];

export const SimulatorScreen: React.FC<SimulatorScreenProps> = ({ navigation }) => {
  const { isBackendConnected, backendUrl } = useSettings();

  // Selected scenario for modal
  const [selectedScenario, setSelectedScenario] = useState<ScenarioMetadata | null>(null);
  const [modalVisible, setModalVisible] = useState<boolean>(false);

  // Alert storm controls
  const [stormCount, setStormCount] = useState<number>(500);
  const [stormSpeed, setStormSpeed] = useState<"slow" | "normal" | "fast">("normal");
  const [stormSeverity, setStormSeverity] = useState<"mixed" | "critical" | "high" | "medium">("mixed");

  const handlePressScenario = (scenario: ScenarioMetadata) => {
    if (!isBackendConnected) {
      Alert.alert(
        "Backend Offline",
        `Cannot start simulation. The backend at ${backendUrl} is unreachable. Please verify your backend server is running and check Settings.`,
        [
          { text: "Cancel", style: "cancel" },
          { text: "Settings", onPress: () => navigation.navigate("Settings") },
        ]
      );
      return;
    }

    // If high-volume (>100 alerts), show confirmation modal
    if (scenario.defaultAlertCount >= 200 || scenario.id === "alert_storm") {
      setSelectedScenario(scenario);
      setModalVisible(true);
    } else {
      executeSimulation(scenario);
    }
  };

  const [securityLoading, setSecurityLoading] = useState<string | null>(null);

  const handleRunSecurityTest = async (scenKey: string, scenTitle: string, expectedDesc: string) => {
    if (!isBackendConnected) {
      Alert.alert("Backend Offline", "Please connect to the backend server in Settings before running security tests.");
      return;
    }
    setSecurityLoading(scenKey);
    try {
      const client = createApiClient(backendUrl);
      const res = await client.runSecurityTest(scenKey);
      const outcome = res?.result?.decision || "BLOCKED";
      const score = res?.result?.trust_score ?? 0;
      const reason = res?.result?.reason || "Check completed";

      Alert.alert(
        `Security Test: ${scenTitle}`,
        `Expected: ${expectedDesc}\n\nShield Decision: ${outcome}\nTrust Score: ${score}/100\nReason: ${reason}`,
        [{ text: "OK" }]
      );
    } catch (e: any) {
      Alert.alert("Security Test Error", e.message || "Failed to execute test");
    } finally {
      setSecurityLoading(null);
    }
  };

  const executeSimulation = (scenario: ScenarioMetadata) => {
    setModalVisible(false);
    navigation.navigate("Progress", {
      scenarioId: scenario.id,
      scenarioName: scenario.name,
      totalCount: scenario.id === "alert_storm" ? stormCount : scenario.defaultAlertCount,
      params: scenario.id === "alert_storm" ? { alertCount: stormCount, speed: stormSpeed, severity: stormSeverity } : undefined,
    });
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Introduction Card */}
      <View style={styles.introCard}>
        <Text style={styles.introTitle}>Alert Scenario Simulator</Text>
        <Text style={styles.introDescription}>
          Select an incident scenario below to inject realistic alert traffic into the Alert Fatigue Buster pipeline. Telemetry updates on the web dashboard in real time.
        </Text>
      </View>

      {/* Storm Configuration Parameters Card (Collapsible/Inline for Alert Storm) */}
      <View style={styles.configCard}>
        <Text style={styles.configTitle}>Alert Storm Parameters</Text>
        
        {/* Count Selector */}
        <Text style={styles.configLabel}>Burst Volume:</Text>
        <View style={styles.chipsRow}>
          {[100, 250, 500, 1000].map((c) => (
            <TouchableOpacity
              key={c}
              style={[styles.chip, stormCount === c && styles.chipActive]}
              onPress={() => setStormCount(c)}
            >
              <Text style={[styles.chipText, stormCount === c && styles.chipTextActive]}>
                {c} Alerts
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Speed Selector */}
        <Text style={styles.configLabel}>Injection Velocity:</Text>
        <View style={styles.chipsRow}>
          {(["slow", "normal", "fast"] as const).map((s) => (
            <TouchableOpacity
              key={s}
              style={[styles.chip, stormSpeed === s && styles.chipActive]}
              onPress={() => setStormSpeed(s)}
            >
              <Text style={[styles.chipText, stormSpeed === s && styles.chipTextActive]}>
                {s.toUpperCase()}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Scenarios List */}
      <Text style={styles.sectionTitle}>Available Scenarios ({SCENARIOS.length})</Text>
      {SCENARIOS.map((scen) => (
        <ScenarioCard
          key={scen.id}
          scenario={scen}
          onPressStart={handlePressScenario}
        />
      ))}

      {/* Alert Integrity Shield Security Test Suite */}
      <View style={styles.securitySection}>
        <Text style={styles.sectionTitle}>Alert Integrity Shield — Security Test Suite</Text>
        <Text style={styles.securitySubtext}>
          Demonstrate end-to-end security protections against injection attacks, replay attempts, and forged signatures without exposing secrets.
        </Text>

        <View style={styles.securityGrid}>
          {[
            {
              id: "valid_alert",
              label: "[VALID ALERT]",
              desc: "HMAC signed + fresh timestamp + nonce",
              expected: "ACCEPTED (Trust 95+)",
              color: "#10b981",
            },
            {
              id: "invalid_signature",
              label: "[INVALID SIGNATURE]",
              desc: "Tampered or corrupted HMAC signature",
              expected: "BLOCKED (401)",
              color: "#ef4444",
            },
            {
              id: "replay_attack",
              label: "[REPLAY ATTACK TEST]",
              desc: "Duplicate request nonce reused",
              expected: "BLOCKED (409)",
              color: "#f97316",
            },
            {
              id: "alert_flood",
              label: "[ALERT FLOOD TEST]",
              desc: "Burst rate exceeding 5000 req/min",
              expected: "THROTTLED (429)",
              color: "#8b5cf6",
            },
            {
              id: "unknown_source",
              label: "[UNKNOWN SOURCE]",
              desc: "Unregistered external sender",
              expected: "QUARANTINED (Trust <40)",
              color: "#f59e0b",
            },
            {
              id: "malformed_payload",
              label: "[MALFORMED PAYLOAD]",
              desc: "Corrupted JSON syntax and bounds",
              expected: "REJECTED (400)",
              color: "#dc2626",
            },
            {
              id: "critical_suspicious",
              label: "[CRITICAL SUSPICIOUS ALERT]",
              desc: "Critical severity alert with volume anomaly",
              expected: "QUARANTINED & PRESERVED (Never dropped!)",
              color: "#6366f1",
            },
          ].map((sec) => (
            <TouchableOpacity
              key={sec.id}
              style={[styles.securityButton, { borderColor: sec.color }]}
              onPress={() => handleRunSecurityTest(sec.id, sec.label, sec.expected)}
              disabled={securityLoading !== null}
            >
              <View style={styles.secBtnHeader}>
                <Text style={[styles.secBtnLabel, { color: sec.color }]}>{sec.label}</Text>
                {securityLoading === sec.id && <Text style={styles.secLoadingText}>Testing...</Text>}
              </View>
              <Text style={styles.secBtnDesc}>{sec.desc}</Text>
              <Text style={styles.secBtnExpected}>Expected: {sec.expected}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Confirmation Modal */}
      <ConfirmationModal
        visible={modalVisible}
        scenario={selectedScenario}
        alertCountOverride={selectedScenario?.id === "alert_storm" ? stormCount : undefined}
        onConfirm={() => selectedScenario && executeSimulation(selectedScenario)}
        onCancel={() => setModalVisible(false)}
      />
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
  introCard: {
    backgroundColor: colors.surface,
    padding: spacing.md,
    borderRadius: radius.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  introTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: colors.text,
    marginBottom: 4,
  },
  introDescription: {
    fontSize: 12,
    color: colors.textSecondary,
    lineHeight: 17,
  },
  configCard: {
    backgroundColor: colors.surface,
    padding: spacing.md,
    borderRadius: radius.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  configTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: colors.text,
    marginBottom: spacing.sm,
    textTransform: "uppercase",
    letterSpacing: 0.3,
  },
  configLabel: {
    fontSize: 11,
    fontWeight: "600",
    color: colors.textSecondary,
    marginTop: spacing.xs,
    marginBottom: spacing.xs,
  },
  chipsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
    marginBottom: spacing.xs,
  },
  chip: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm + 2,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceSubtle,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  chipText: {
    fontSize: 11,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  chipTextActive: {
    color: "#ffffff",
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: "700",
    color: colors.textSecondary,
    textTransform: "uppercase",
    letterSpacing: 0.4,
    marginTop: spacing.xs,
    marginBottom: spacing.sm,
  },
  securitySection: {
    backgroundColor: colors.surface,
    padding: spacing.md,
    borderRadius: radius.md,
    marginTop: spacing.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  securitySubtext: {
    fontSize: 11,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
    lineHeight: 15,
  },
  securityGrid: {
    gap: spacing.sm,
  },
  securityButton: {
    backgroundColor: colors.surfaceSubtle,
    borderWidth: 1.5,
    borderRadius: radius.md,
    padding: spacing.sm,
  },
  secBtnHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 2,
  },
  secBtnLabel: {
    fontSize: 12,
    fontWeight: "700",
    fontFamily: Platform.OS === "ios" ? "Courier" : "monospace",
  },
  secLoadingText: {
    fontSize: 10,
    color: colors.primary,
    fontWeight: "600",
  },
  secBtnDesc: {
    fontSize: 11,
    color: colors.text,
    marginBottom: 4,
  },
  secBtnExpected: {
    fontSize: 10,
    color: colors.textSecondary,
    fontFamily: Platform.OS === "ios" ? "Courier" : "monospace",
  },
});

