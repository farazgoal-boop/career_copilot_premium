import React from 'react';
import {StyleSheet, Text, View} from 'react-native';

export function StatusHeader(): React.JSX.Element {
  return (
    <View style={styles.container}>
      <Text style={styles.eyebrow}>Career Copilot Premium</Text>
      <Text style={styles.title}>Link your phone</Text>
      <Text style={styles.body}>
        Open Link Device on desktop, then scan the QR or enter the 6-digit code here.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: 8,
    paddingBottom: 4,
  },
  eyebrow: {
    color: '#f3b53f',
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
  },
  title: {
    color: '#f4f7f9',
    fontSize: 32,
    fontWeight: '800',
    letterSpacing: -0.6,
  },
  body: {
    color: '#b6c4cb',
    fontSize: 15,
    lineHeight: 23,
    maxWidth: 320,
  },
});