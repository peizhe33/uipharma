import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

Future<void> setOskVisible(bool visible) async {
  try {
    await Process.run('dbus-send', [
      '--session',
      '--type=method_call',
      '--dest=org.onboard.Onboard',
      '/org/onboard/Onboard/Keyboard',
      'org.onboard.Onboard.Keyboard.${visible ? 'Show' : 'Hide'}',
    ]);
  } catch (_) {}
}

Timer? _oskHideTimer;

void _showOsk() {
  _oskHideTimer?.cancel();
  setOskVisible(true);
}

void _scheduleOskHide() {
  _oskHideTimer?.cancel();
  _oskHideTimer = Timer(const Duration(milliseconds: 150), () {
    final primaryFocus = FocusManager.instance.primaryFocus;
    final focusedWidget = primaryFocus?.context?.widget;
    if (focusedWidget is! EditableText) {
      setOskVisible(false);
    }
  });
}

class OskTextField extends StatefulWidget {
  final TextEditingController? controller;
  final InputDecoration? decoration;
  final ValueChanged<String>? onChanged;
  final bool obscureText;
  final TextInputType? keyboardType;
  final int? maxLength;
  final List<TextInputFormatter>? inputFormatters;
  final bool autofocus;
  final TextAlign textAlign;
  final TextStyle? style;
  final ValueChanged<String>? onSubmitted;
  final TextCapitalization textCapitalization;
  final GestureTapCallback? onTap;
  final TextInputAction? textInputAction;
  final bool enabled;
  final bool readOnly;
  final int? minLines;
  final int? maxLines;
  final bool expands;
  final TextAlignVertical? textAlignVertical;

  const OskTextField({
    super.key,
    this.controller,
    this.decoration,
    this.onChanged,
    this.obscureText = false,
    this.keyboardType,
    this.maxLength,
    this.inputFormatters,
    this.autofocus = false,
    this.textAlign = TextAlign.start,
    this.style,
    this.onSubmitted,
    this.textCapitalization = TextCapitalization.none,
    this.onTap,
    this.textInputAction,
    this.enabled = true,
    this.readOnly = false,
    this.minLines,
    this.maxLines = 1,
    this.expands = false,
    this.textAlignVertical,
  });

  @override
  State<OskTextField> createState() => _OskTextFieldState();
}

class _OskTextFieldState extends State<OskTextField> {
  late final FocusNode _focus;

  @override
  void initState() {
    super.initState();
    _focus = FocusNode()..addListener(_handleFocusChanged);
  }

  void _handleFocusChanged() {
    if (_focus.hasFocus) {
      _showOsk();
    } else {
      _scheduleOskHide();
    }
  }

  @override
  void dispose() {
    _focus
      ..removeListener(_handleFocusChanged)
      ..dispose();
    _scheduleOskHide();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: widget.controller,
      focusNode: _focus,
      decoration: widget.decoration,
      onChanged: widget.onChanged,
      obscureText: widget.obscureText,
      keyboardType: widget.keyboardType,
      maxLength: widget.maxLength,
      inputFormatters: widget.inputFormatters,
      autofocus: widget.autofocus,
      textAlign: widget.textAlign,
      style: widget.style,
      onSubmitted: widget.onSubmitted,
      textCapitalization: widget.textCapitalization,
      textInputAction: widget.textInputAction,
      enabled: widget.enabled,
      readOnly: widget.readOnly,
      minLines: widget.minLines,
      maxLines: widget.maxLines,
      expands: widget.expands,
      textAlignVertical: widget.textAlignVertical,
      onTap: () {
        _showOsk();
        widget.onTap?.call();
      },
    );
  }
}

class OskTextFormField extends StatefulWidget {
  final TextEditingController? controller;
  final InputDecoration? decoration;
  final ValueChanged<String>? onChanged;
  final bool obscureText;
  final TextInputType? keyboardType;
  final int? maxLength;
  final List<TextInputFormatter>? inputFormatters;
  final bool autofocus;
  final TextAlign textAlign;
  final TextStyle? style;
  final ValueChanged<String>? onSubmitted;
  final TextCapitalization textCapitalization;
  final GestureTapCallback? onTap;
  final TextInputAction? textInputAction;
  final bool enabled;
  final bool readOnly;
  final int? minLines;
  final int? maxLines;
  final bool expands;
  final TextAlignVertical? textAlignVertical;
  final String? initialValue;
  final FormFieldValidator<String>? validator;
  final FormFieldSetter<String>? onSaved;
  final AutovalidateMode? autovalidateMode;

  const OskTextFormField({
    super.key,
    this.controller,
    this.decoration,
    this.onChanged,
    this.obscureText = false,
    this.keyboardType,
    this.maxLength,
    this.inputFormatters,
    this.autofocus = false,
    this.textAlign = TextAlign.start,
    this.style,
    this.onSubmitted,
    this.textCapitalization = TextCapitalization.none,
    this.onTap,
    this.textInputAction,
    this.enabled = true,
    this.readOnly = false,
    this.minLines,
    this.maxLines = 1,
    this.expands = false,
    this.textAlignVertical,
    this.initialValue,
    this.validator,
    this.onSaved,
    this.autovalidateMode,
  }) : assert(
          initialValue == null || controller == null,
          'Either controller or initialValue can be specified, not both.',
        );

  @override
  State<OskTextFormField> createState() => _OskTextFormFieldState();
}

class _OskTextFormFieldState extends State<OskTextFormField> {
  late final FocusNode _focus;
  final _formFieldKey = GlobalKey<FormFieldState<String>>();

  @override
  void initState() {
    super.initState();
    _focus = FocusNode()..addListener(_handleFocusChanged);
    widget.controller?.addListener(_handleControllerChanged);
  }

  @override
  void didUpdateWidget(covariant OskTextFormField oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.controller != widget.controller) {
      oldWidget.controller?.removeListener(_handleControllerChanged);
      widget.controller?.addListener(_handleControllerChanged);
      _syncFormValue();
    }
  }

  void _handleControllerChanged() {
    _syncFormValue();
  }

  void _syncFormValue() {
    final formFieldState = _formFieldKey.currentState;
    if (formFieldState != null) {
      formFieldState.didChange(widget.controller?.text ?? '');
    }
  }

  void _handleFocusChanged() {
    if (_focus.hasFocus) {
      _showOsk();
    } else {
      _scheduleOskHide();
    }
  }

  @override
  void dispose() {
    widget.controller?.removeListener(_handleControllerChanged);
    _focus
      ..removeListener(_handleFocusChanged)
      ..dispose();
    _scheduleOskHide();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FormField<String>(
      key: _formFieldKey,
      initialValue: widget.controller?.text ?? widget.initialValue,
      validator: widget.validator,
      onSaved: widget.onSaved,
      autovalidateMode: widget.autovalidateMode,
      enabled: widget.enabled,
      builder: (state) {
        final decoration = (widget.decoration ?? const InputDecoration())
            .copyWith(errorText: state.errorText);
        return TextField(
          controller: widget.controller,
          focusNode: _focus,
          decoration: decoration,
          onChanged: (value) {
            state.didChange(value);
            widget.onChanged?.call(value);
          },
          obscureText: widget.obscureText,
          keyboardType: widget.keyboardType,
          maxLength: widget.maxLength,
          inputFormatters: widget.inputFormatters,
          autofocus: widget.autofocus,
          textAlign: widget.textAlign,
          style: widget.style,
          onSubmitted: widget.onSubmitted,
          textCapitalization: widget.textCapitalization,
          textInputAction: widget.textInputAction,
          enabled: widget.enabled,
          readOnly: widget.readOnly,
          minLines: widget.minLines,
          maxLines: widget.maxLines,
          expands: widget.expands,
          textAlignVertical: widget.textAlignVertical,
          onTap: () {
            _showOsk();
            widget.onTap?.call();
          },
        );
      },
    );
  }
}
