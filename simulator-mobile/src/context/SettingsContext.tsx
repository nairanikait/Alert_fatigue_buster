import React, { createContext, useContext, useState, useEffect } from "react";
import { Platform } from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import axios from "axios";
import { SimulationHistoryItem } from "../types/simulator";

interface SettingsContextType {
  backendUrl: string;
  setBackendUrl: (url: string) => Promise<void>;
  dashboardUrl: string;
  setDashboardUrl: (url: string) => Promise<void>;
  isBackendConnected: boolean;
  isCheckingConnection: boolean;
  checkConnection: () => Promise<boolean>;
  history: SimulationHistoryItem[];
  addHistoryItem: (item: SimulationHistoryItem) => Promise<void>;
  clearHistory: () => Promise<void>;
}

const SETTINGS_KEY = "@alert_buster_backend_url";
const DASHBOARD_KEY = "@alert_buster_dashboard_url";
const HISTORY_KEY = "@alert_buster_history";

const DEFAULT_BACKEND_URL =
  Platform.OS === "android" ? "http://10.0.2.2:8000" : "http://localhost:8000";

const DEFAULT_DASHBOARD_URL =
  Platform.OS === "android" ? "http://10.0.2.2:5173" : "http://localhost:5173";

const SettingsContext = createContext<SettingsContextType>({
  backendUrl: DEFAULT_BACKEND_URL,
  setBackendUrl: async () => {},
  dashboardUrl: DEFAULT_DASHBOARD_URL,
  setDashboardUrl: async () => {},
  isBackendConnected: false,
  isCheckingConnection: false,
  checkConnection: async () => false,
  history: [],
  addHistoryItem: async () => {},
  clearHistory: async () => {},
});

export const SettingsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [backendUrl, setBackendUrlState] = useState<string>(DEFAULT_BACKEND_URL);
  const [dashboardUrl, setDashboardUrlState] = useState<string>(DEFAULT_DASHBOARD_URL);
  const [isBackendConnected, setIsBackendConnected] = useState<boolean>(false);
  const [isCheckingConnection, setIsCheckingConnection] = useState<boolean>(false);
  const [history, setHistory] = useState<SimulationHistoryItem[]>([]);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const savedUrl = await AsyncStorage.getItem(SETTINGS_KEY);
      const savedDashboard = await AsyncStorage.getItem(DASHBOARD_KEY);
      const savedHistory = await AsyncStorage.getItem(HISTORY_KEY);

      const activeUrl = savedUrl || DEFAULT_BACKEND_URL;
      setBackendUrlState(activeUrl);

      if (savedDashboard) setDashboardUrlState(savedDashboard);
      if (savedHistory) {
        setHistory(JSON.parse(savedHistory));
      }

      // Check initial connection
      testConnectionTo(activeUrl);
    } catch (err) {
      console.warn("Failed to load settings:", err);
    }
  };

  const testConnectionTo = async (url: string): Promise<boolean> => {
    setIsCheckingConnection(true);
    try {
      const res = await axios.get(`${url.replace(/\/+$/, "")}/health`, {
        timeout: 4000,
      });
      const ok = res.status === 200 && res.data?.status === "ok";
      setIsBackendConnected(ok);
      return ok;
    } catch (err) {
      setIsBackendConnected(false);
      return false;
    } finally {
      setIsCheckingConnection(false);
    }
  };

  const setBackendUrl = async (url: string) => {
    const cleanUrl = url.trim().replace(/\/+$/, "");
    setBackendUrlState(cleanUrl);
    await AsyncStorage.setItem(SETTINGS_KEY, cleanUrl);
    await testConnectionTo(cleanUrl);
  };

  const setDashboardUrl = async (url: string) => {
    const cleanUrl = url.trim().replace(/\/+$/, "");
    setDashboardUrlState(cleanUrl);
    await AsyncStorage.setItem(DASHBOARD_KEY, cleanUrl);
  };

  const checkConnection = async (): Promise<boolean> => {
    return await testConnectionTo(backendUrl);
  };

  const addHistoryItem = async (item: SimulationHistoryItem) => {
    const updated = [item, ...history].slice(0, 50); // Keep last 50
    setHistory(updated);
    await AsyncStorage.setItem(HISTORY_KEY, JSON.stringify(updated));
  };

  const clearHistory = async () => {
    setHistory([]);
    await AsyncStorage.removeItem(HISTORY_KEY);
  };

  return (
    <SettingsContext.Provider
      value={{
        backendUrl,
        setBackendUrl,
        dashboardUrl,
        setDashboardUrl,
        isBackendConnected,
        isCheckingConnection,
        checkConnection,
        history,
        addHistoryItem,
        clearHistory,
      }}
    >
      {children}
    </SettingsContext.Provider>
  );
};

export const useSettings = () => useContext(SettingsContext);
