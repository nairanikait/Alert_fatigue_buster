import React from "react";
import { View, Text, StyleSheet, Modal, TouchableOpacity } from "react-native";
import { colors, spacing, radius } from "../constants/theme";
import { ScenarioMetadata } from "../types/simulator";

interface ConfirmationModalProps {
  visible: boolean;
  scenario: ScenarioMetadata | null;
  alertCountOverride?: number;
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmationModal: React.FC<ConfirmationModalProps> = ({
  visible,
  scenario,
  alertCountOverride,
  onConfirm,
  onCancel,
}) => {
  if (!scenario) return null;

  const count = alertCountOverride || scenario.defaultAlertCount;

  return (
    <Modal
      transparent
      animationType="fade"
      visible={visible}
      onRequestClose={onCancel}
    >
      <View style={styles.overlay}>
        <View style={styles.dialog}>
          <Text style={styles.title}>Start Simulation?</Text>
          <Text style={styles.subtitle}>
            You are about to launch <Text style={styles.highlight}>{scenario.name}</Text>.
          </Text>

          <View style={styles.infoBox}>
            <Text style={styles.infoText}>
              This will generate approximately <Text style={styles.bold}>{count} alert events</Text> and send them to the backend alert intelligence pipeline for deduplication and correlation.
            </Text>
          </View>

          <View style={styles.actionsRow}>
            <TouchableOpacity
              style={styles.cancelButton}
              onPress={onCancel}
              activeOpacity={0.7}
            >
              <Text style={styles.cancelText}>Cancel</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.confirmButton}
              onPress={onConfirm}
              activeOpacity={0.8}
            >
              <Text style={styles.confirmText}>Start Simulation</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.6)",
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.xl,
  },
  dialog: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.xl,
    width: "100%",
    maxWidth: 360,
    borderWidth: 1,
    borderColor: colors.border,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 5,
  },
  title: {
    fontSize: 17,
    fontWeight: "700",
    color: colors.text,
    marginBottom: spacing.xs,
  },
  subtitle: {
    fontSize: 13,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  highlight: {
    color: colors.primary,
    fontWeight: "700",
  },
  infoBox: {
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radius.sm,
    padding: spacing.md,
    marginBottom: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  infoText: {
    fontSize: 12,
    color: colors.textSecondary,
    lineHeight: 17,
  },
  bold: {
    fontWeight: "700",
    color: colors.text,
  },
  actionsRow: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: spacing.sm,
  },
  cancelButton: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceSubtle,
  },
  cancelText: {
    fontSize: 12,
    fontWeight: "600",
    color: colors.textSecondary,
  },
  confirmButton: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.sm,
    backgroundColor: colors.primary,
  },
  confirmText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#ffffff",
  },
});
