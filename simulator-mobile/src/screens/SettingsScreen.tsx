import React, { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  ScrollView,
  Alert,
  ActivityIndicator,
  Platform,
} from "react-native";
import { colors, spacing, radius } from "../constants/theme";
import { useSettings } from "../context/SettingsContext";
import { createApiClient } from "../api/client";

export const SettingsScreen: React.FC = () => {
  const {
    backendUrl,
    setBackendUrl,
    dashboardUrl,
    setDashboardUrl,
    isBackendConnected,
    isCheckingConnection,
    checkConnection,
  } = useSettings();

  const [inputUrl, setInputUrl] = useState<string>(backendUrl);
  const [inputDashboard, setInputDashboard] = useState<string>(dashboardUrl);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [isResetting, setIsResetting] = useState<boolean>(false);

  const handleSave = async () => {
    await setBackendUrl(inputUrl);
    await setDashboardUrl(inputDashboard);
    const ok = await checkConnection();
    setTestResult(ok ? "✓ Connection Successful" : "✕ Unable to reach backend");
  };

  const handleSetPreset = (url: string) => {
    setInputUrl(url);
  };

  const handleTestPing = async () => {
    setTestResult("Pinging backend...");
    const client = createApiClient(inputUrl);
    const ok = await client.checkHealth();
    setTestResult(ok ? "✓ Backend Connected (200 OK)" : "✕ Backend Offline (Timeout/Refused)");
  };

  const handleResetBackendData = async () => {
    Alert.alert(
      "Reset Backend Telemetry",
      "This will purge all alerts, incidents, and notifications in the backend SQLite database for clean demo presentation. Proceed?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Reset All",
          style: "destructive",
          onPress: async () => {
            try {
              setIsResetting(true);
              const client = createApiClient(backendUrl);
              await client.resetData();
              Alert.alert("Success", "Backend database telemetry has been reset.");
            } catch (err: any) {
              Alert.alert("Error", `Failed to reset: ${err.message}`);
            } finally {
              setIsResetting(false);
            }
          },
        },
      ]
    );
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Title */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Backend Network Configuration</Text>
        <Text style={styles.cardDesc}>
          Specify the address of your Alert Fatigue Buster FastAPI backend. Do not use localhost on physical phones.
        </Text>

        {/* URL Input */}
        <Text style={styles.inputLabel}>Backend API Base URL</Text>
        <TextInput
          style={styles.input}
          value={inputUrl}
          onChangeText={setInputUrl}
          placeholder="http://192.168.1.X:8000"
          placeholderTextColor={colors.textMuted}
          autoCapitalize="none"
          autoCorrect={false}
        />

        {/* Quick Presets */}
        <Text style={styles.presetLabel}>Quick Presets:</Text>
        <View style={styles.presetRow}>
          <TouchableOpacity
            style={styles.presetButton}
            onPress={() => handleSetPreset("http://localhost:8000")}
          >
            <Text style={styles.presetText}>iOS Simulator</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.presetButton}
            onPress={() => handleSetPreset("http://10.0.2.2:8000")}
          >
            <Text style={styles.presetText}>Android Emulator</Text>
          </TouchableOpacity>
        </View>

        {/* Dashboard URL Input */}
        <Text style={[styles.inputLabel, { marginTop: spacing.md }]}>Web Dashboard URL</Text>
        <TextInput
          style={styles.input}
          value={inputDashboard}
          onChangeText={setInputDashboard}
          placeholder="http://localhost:5173"
          placeholderTextColor={colors.textMuted}
          autoCapitalize="none"
          autoCorrect={false}
        />

        {/* Actions */}
        <View style={styles.actionsRow}>
          <TouchableOpacity
            style={styles.testButton}
            onPress={handleTestPing}
            disabled={isCheckingConnection}
          >
            {isCheckingConnection ? (
              <ActivityIndicator size="small" color={colors.primary} />
            ) : (
              <Text style={styles.testButtonText}>Test Connection</Text>
            )}
          </TouchableOpacity>

          <TouchableOpacity style={styles.saveButton} onPress={handleSave}>
            <Text style={styles.saveButtonText}>Save Settings</Text>
          </TouchableOpacity>
        </View>

        {testResult && (
          <View
            style={[
              styles.resultBox,
              testResult.includes("✓") ? styles.resultSuccess : styles.resultError,
            ]}
          >
            <Text
              style={[
                styles.resultText,
                testResult.includes("✓") ? styles.textSuccess : styles.textError,
              ]}
            >
              {testResult}
            </Text>
          </View>
        )}
      </View>

      {/* Danger Zone: Reset Telemetry */}
      <View style={[styles.card, styles.dangerCard]}>
        <Text style={styles.dangerTitle}>Demonstration Utilities</Text>
        <Text style={styles.cardDesc}>
          Purge all recorded alerts, correlated incidents, and dispatched notifications from the database before starting a live presentation.
        </Text>

        <TouchableOpacity
          style={styles.dangerButton}
          onPress={handleResetBackendData}
          disabled={isResetting}
        >
          {isResetting ? (
            <ActivityIndicator size="small" color="#ffffff" />
          ) : (
            <Text style={styles.dangerButtonText}>Purge All Backend Telemetry</Text>
          )}
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
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: "800",
    color: colors.text,
    marginBottom: 4,
  },
  cardDesc: {
    fontSize: 12,
    color: colors.textSecondary,
    lineHeight: 17,
    marginBottom: spacing.md,
  },
  inputLabel: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.textSecondary,
    marginBottom: 4,
    textTransform: "uppercase",
    letterSpacing: 0.3,
  },
  input: {
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm + 2,
    borderWidth: 1,
    borderColor: colors.border,
    fontSize: 13,
    color: colors.text,
    fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace",
  },
  presetLabel: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: spacing.sm,
    marginBottom: spacing.xs,
  },
  presetRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  presetButton: {
    backgroundColor: colors.surfaceSubtle,
    paddingHorizontal: spacing.sm + 2,
    paddingVertical: spacing.xs,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  presetText: {
    fontSize: 11,
    color: colors.primary,
    fontWeight: "600",
  },
  actionsRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  testButton: {
    flex: 1,
    backgroundColor: colors.surfaceSubtle,
    paddingVertical: spacing.sm + 2,
    borderRadius: radius.sm,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.border,
  },
  testButtonText: {
    fontSize: 12,
    fontWeight: "700",
    color: colors.primary,
  },
  saveButton: {
    flex: 1,
    backgroundColor: colors.primary,
    paddingVertical: spacing.sm + 2,
    borderRadius: radius.sm,
    alignItems: "center",
    justifyContent: "center",
  },
  saveButtonText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#ffffff",
  },
  resultBox: {
    marginTop: spacing.md,
    padding: spacing.sm + 2,
    borderRadius: radius.sm,
    borderWidth: 1,
  },
  resultSuccess: {
    backgroundColor: colors.successLight,
    borderColor: colors.successBorder,
  },
  resultError: {
    backgroundColor: colors.criticalLight,
    borderColor: colors.criticalBorder,
  },
  resultText: {
    fontSize: 12,
    fontWeight: "700",
    textAlign: "center",
  },
  textSuccess: {
    color: colors.success,
  },
  textError: {
    color: colors.critical,
  },
  dangerCard: {
    borderColor: colors.criticalBorder,
  },
  dangerTitle: {
    fontSize: 14,
    fontWeight: "800",
    color: colors.critical,
    marginBottom: 4,
  },
  dangerButton: {
    backgroundColor: colors.critical,
    borderRadius: radius.sm,
    paddingVertical: spacing.sm + 2,
    alignItems: "center",
  },
  dangerButtonText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#ffffff",
  },
});
