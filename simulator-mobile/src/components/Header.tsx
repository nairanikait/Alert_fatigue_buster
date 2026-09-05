import React from "react";
import { View, Text, StyleSheet, TouchableOpacity, Platform } from "react-native";
import { colors, spacing, radius } from "../constants/theme";
import { useSettings } from "../context/SettingsContext";

interface HeaderProps {
  onPressSettings?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onPressSettings }) => {
  const { isBackendConnected, backendUrl, checkConnection, isCheckingConnection } = useSettings();

  return (
    <View style={styles.container}>
      <View style={styles.titleRow}>
        <View>
          <Text style={styles.brandTitle}>Alert Fatigue Buster</Text>
          <Text style={styles.subTitle}>Simulator & Stress Tester</Text>
        </View>

        <TouchableOpacity
          onPress={onPressSettings || checkConnection}
          activeOpacity={0.7}
          style={[
            styles.statusBadge,
            isBackendConnected ? styles.statusOnline : styles.statusOffline,
          ]}
        >
          <View
            style={[
              styles.statusDot,
              isBackendConnected ? styles.dotOnline : styles.dotOffline,
            ]}
          />
          <Text
            style={[
              styles.statusText,
              isBackendConnected ? styles.textOnline : styles.textOffline,
            ]}
          >
            {isCheckingConnection
              ? "Checking..."
              : isBackendConnected
              ? "Connected"
              : "Offline"}
          </Text>
        </TouchableOpacity>
      </View>

      <Text style={styles.urlText}>
        Target: <Text style={styles.urlHighlight}>{backendUrl}</Text>
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  titleRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  brandTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: colors.text,
    letterSpacing: -0.3,
  },
  subTitle: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  statusBadge: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.sm + 2,
    paddingVertical: spacing.xs,
    borderRadius: radius.full,
    borderWidth: 1,
  },
  statusOnline: {
    backgroundColor: colors.successLight,
    borderColor: colors.successBorder,
  },
  statusOffline: {
    backgroundColor: colors.criticalLight,
    borderColor: colors.criticalBorder,
  },
  statusDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    marginRight: 5,
  },
  dotOnline: {
    backgroundColor: colors.success,
  },
  dotOffline: {
    backgroundColor: colors.critical,
  },
  statusText: {
    fontSize: 11,
    fontWeight: "600",
  },
  textOnline: {
    color: colors.success,
  },
  textOffline: {
    color: colors.critical,
  },
  urlText: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: spacing.sm,
    fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace",
  },
  urlHighlight: {
    color: colors.primary,
    fontWeight: "600",
  },
});
