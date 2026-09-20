import 'dart:math' as math;

import 'package:flutter/material.dart';

class Responsive {
  static bool isCompact(BuildContext context) =>
      MediaQuery.sizeOf(context).width < 640;

  static bool isNarrow(BuildContext context) =>
      MediaQuery.sizeOf(context).width < 820;

  static EdgeInsets pagePadding(BuildContext context) {
    final size = MediaQuery.sizeOf(context);
    final horizontal = size.width < 380
        ? 14.0
        : size.width < 640
            ? 18.0
            : 24.0;
    final vertical = size.height < 620 ? 14.0 : 24.0;
    return EdgeInsets.symmetric(horizontal: horizontal, vertical: vertical);
  }

  static double scale(
    BuildContext context,
    double value, {
    double min = 0.82,
    double max = 1.0,
  }) {
    final width = MediaQuery.sizeOf(context).width;
    final factor = (width / 430).clamp(min, max).toDouble();
    return value * factor;
  }

  static double gap(BuildContext context, double value) =>
      scale(context, value, min: 0.62);
}

class ResponsiveCenter extends StatelessWidget {
  final Widget child;
  final double maxWidth;
  final EdgeInsetsGeometry? padding;
  final bool scrollable;

  const ResponsiveCenter({
    super.key,
    required this.child,
    this.maxWidth = 900,
    this.padding,
    this.scrollable = true,
  });

  @override
  Widget build(BuildContext context) {
    final content = Center(
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: maxWidth),
        child: child,
      ),
    );

    if (!scrollable) {
      return Padding(
        padding: padding ?? Responsive.pagePadding(context),
        child: content,
      );
    }

    final insets = MediaQuery.viewInsetsOf(context);
    return SingleChildScrollView(
      padding: (padding ?? Responsive.pagePadding(context))
          .add(EdgeInsets.only(bottom: insets.bottom)),
      child: content,
    );
  }
}

class ResponsiveTwoColumn extends StatelessWidget {
  final Widget left;
  final Widget right;
  final double breakpoint;
  final double gap;
  final int leftFlex;
  final int rightFlex;

  const ResponsiveTwoColumn({
    super.key,
    required this.left,
    required this.right,
    this.breakpoint = 760,
    this.gap = 16,
    this.leftFlex = 1,
    this.rightFlex = 1,
  });

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxWidth < breakpoint) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              left,
              SizedBox(height: gap),
              right,
            ],
          );
        }

        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(flex: leftFlex, child: left),
            SizedBox(width: gap),
            Expanded(flex: rightFlex, child: right),
          ],
        );
      },
    );
  }
}

class ResponsiveWrap extends StatelessWidget {
  final List<Widget> children;
  final double minItemWidth;
  final double spacing;
  final double runSpacing;

  const ResponsiveWrap({
    super.key,
    required this.children,
    this.minItemWidth = 180,
    this.spacing = 16,
    this.runSpacing = 18,
  });

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final count = math.max(1, constraints.maxWidth ~/ minItemWidth);
        final width =
            (constraints.maxWidth - (spacing * (count - 1))) / count;

        return Wrap(
          spacing: spacing,
          runSpacing: runSpacing,
          children: children
              .map((child) => SizedBox(width: width, child: child))
              .toList(),
        );
      },
    );
  }
}
