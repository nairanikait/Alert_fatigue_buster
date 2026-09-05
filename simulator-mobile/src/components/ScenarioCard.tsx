import React from "react";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import { colors, spacing, radius } from "../constants/theme";
import { ScenarioMetadata } from "../types/simulator";

interface ScenarioCardProps {
  scenario: ScenarioMetadata;
  onPressStart: (scenario: ScenarioMetadata) => void;
  disabled?: boolean;
}

export const ScenarioCard: React.FC<ScenarioCardProps> = ({
  scenario,
  onPressStart,
  disabled = false,
}) => {
  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <Text style={styles.name}>{scenario.name}</Text>
        <View style={[styles.badge, { backgroundColor: scenario.badgeColor }]}>
          <Text style={[styles.badgeText, { color: scenario.badgeTextColor }]}>
            {scenario.tag}
          </Text>
        </View>
      </View>

      <Text style={styles.description}>{scenario.description}</Text>

      <View style={styles.expectedBox}>
        <Text style={styles.expectedTitle}>Expected Pipeline Behavior:</Text>
        <Text style={styles.expectedText}>{scenario.expectedBehavior}</Text>
      </View>

      <TouchableOpacity
        style={[styles.button, disabled && styles.buttonDisabled]}
        onPress={() => onPressStart(scenario)}
        disabled={disabled}
        activeOpacity={0.8}
      >
        <Text style={styles.buttonText}>{scenario.buttonText}</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.xs,
  },
  name: {
    fontSize: 15,
    fontWeight: "700",
    color: colors.text,
    letterSpacing: -0.2,
    flex: 1,
  },
  badge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radius.sm,
  },
  badgeText: {
    fontSize: 10,
    fontWeight: "700",
    textTransform: "uppercase",
  },
  description: {
    fontSize: 12,
    color: colors.textSecondary,
    lineHeight: 17,
    marginTop: 2,
  },
  expectedBox: {
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radius.sm,
    padding: spacing.sm + 2,
    marginVertical: spacing.md,
    borderLeftWidth: 3,
    borderLeftColor: colors.primary,
  },
  expectedTitle: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.text,
    marginBottom: 2,
  },
  expectedText: {
    fontSize: 11,
    color: colors.textSecondary,
    lineHeight: 15,
  },
  button: {
    backgroundColor: colors.primary,
    borderRadius: radius.sm,
    paddingVertical: spacing.sm + 2,
    alignItems: "center",
    justifyContent: "center",
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  buttonText: {
    color: "#ffffff",
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.2,
  },
});
