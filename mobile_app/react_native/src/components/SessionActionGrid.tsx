import React from 'react';
import {Pressable, StyleSheet, Text, View} from 'react-native';

import {LiveBridgeAction} from '../types';

type SessionActionGridProps = {
  actions: LiveBridgeAction[];
  onPress: (actionId: string) => void | Promise<void>;
};

export function SessionActionGrid({actions, onPress}: SessionActionGridProps): React.JSX.Element {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Session actions</Text>
      <View style={styles.grid}>
        {actions.map(action => (
          <Pressable key={action.action_id} onPress={() => void onPress(action.action_id)} style={styles.button}>
            <Text style={styles.buttonText}>{action.label}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#132129',
    borderColor: '#22333e',
    borderRadius: 20,
    borderWidth: 1,
    gap: 14,
    padding: 16,
  },
  title: {
    color: '#f4f7f9',
    fontSize: 18,
    fontWeight: '700',
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  button: {
    backgroundColor: '#f3b53f',
    borderRadius: 14,
    minWidth: '47%',
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  buttonText: {
    color: '#1a1304',
    fontWeight: '700',
    textAlign: 'center',
  },
});