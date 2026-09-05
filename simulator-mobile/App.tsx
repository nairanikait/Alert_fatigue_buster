import React from "react";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { Text, View, StyleSheet } from "react-native";

import { SettingsProvider } from "./src/context/SettingsContext";
import { Header } from "./src/components/Header";
import { SimulatorScreen } from "./src/screens/SimulatorScreen";
import { ProgressScreen } from "./src/screens/ProgressScreen";
import { ResultScreen } from "./src/screens/ResultScreen";
import { HistoryScreen } from "./src/screens/HistoryScreen";
import { SettingsScreen } from "./src/screens/SettingsScreen";
import { colors } from "./src/constants/theme";

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

const SimulatorStack = () => {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.background },
      }}
    >
      <Stack.Screen name="SimulatorMain" component={SimulatorScreen} />
      <Stack.Screen name="Progress" component={ProgressScreen} />
      <Stack.Screen name="Result" component={ResultScreen} />
    </Stack.Navigator>
  );
};

export default function App() {
  return (
    <SafeAreaProvider>
      <SettingsProvider>
        <NavigationContainer>
          <SafeAreaView style={styles.safeArea} edges={["top", "left", "right"]}>
            <StatusBar style="dark" />
            <Header />
            <View style={styles.navigatorContainer}>
              <Tab.Navigator
                screenOptions={{
                  headerShown: false,
                  tabBarActiveTintColor: colors.primary,
                  tabBarInactiveTintColor: colors.textMuted,
                  tabBarStyle: {
                    backgroundColor: colors.surface,
                    borderTopWidth: 1,
                    borderTopColor: colors.border,
                    height: 60,
                    paddingBottom: 8,
                    paddingTop: 6,
                  },
                  tabBarLabelStyle: {
                    fontSize: 11,
                    fontWeight: "700",
                  },
                }}
              >
                <Tab.Screen
                  name="Simulator"
                  component={SimulatorStack}
                  options={{
                    tabBarLabel: "Simulator",
                    tabBarIcon: ({ color }) => (
                      <Text style={{ color, fontSize: 18, fontWeight: "800" }}>⚡</Text>
                    ),
                  }}
                />
                <Tab.Screen
                  name="History"
                  component={HistoryScreen}
                  options={{
                    tabBarLabel: "History",
                    tabBarIcon: ({ color }) => (
                      <Text style={{ color, fontSize: 18, fontWeight: "800" }}>📋</Text>
                    ),
                  }}
                />
                <Tab.Screen
                  name="Settings"
                  component={SettingsScreen}
                  options={{
                    tabBarLabel: "Settings",
                    tabBarIcon: ({ color }) => (
                      <Text style={{ color, fontSize: 18, fontWeight: "800" }}>⚙</Text>
                    ),
                  }}
                />
              </Tab.Navigator>
            </View>
          </SafeAreaView>
        </NavigationContainer>
      </SettingsProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.surface,
  },
  navigatorContainer: {
    flex: 1,
    backgroundColor: colors.background,
  },
});
