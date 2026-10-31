# On-Screen Keyboard Handoff

## Purpose and environment

This change wires manual Flutter text inputs to the Raspberry Pi's **Onboard**
on-screen keyboard.

- Application: Flutter Linux desktop app
- Target hardware: Raspberry Pi 5
- Display session: X11
- On-screen keyboard: Onboard
- Control mechanism: session D-Bus via `dbus-send`
- D-Bus service: `org.onboard.Onboard`
- D-Bus object path: `/org/onboard/Onboard/Keyboard`
- D-Bus interface: `org.onboard.Onboard.Keyboard`
- Methods:
  - `Show`
  - `Hide`

The implementation is platform-specific in behavior: the wrapper invokes
`dbus-send`, so Onboard must be installed and running in the user's graphical
X11 session.

## Final widget source

The complete final source is also available as
[`osk_text_field.dart.txt`](./osk_text_field.dart.txt).

```dart
import 'dart:io';
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

Future<void> setOskVisible(bool visible) async {
  try {
    await Process.run('dbus-send', [
      '--session', '--type=method_call',
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
```

## Files changed and input replacements

The import added to every changed screen/widget file was:

```dart
import '../widgets/osk_text_field.dart';
```

The import was:

```dart
import 'osk_text_field.dart';
```

inside `lib/widgets/review_notification_bell.dart`.

Line numbers below refer to the final repository version at the time of this
handoff. Re-run the search before applying to a newer version because line
numbers will change.

| File | Line | Old widget | New widget | Import |
|---|---:|---|---|---|
| `lib/screens/current_condition_page.dart` | 278 | `TextFormField` | `OskTextFormField` | Added |
| `lib/screens/current_condition_page.dart` | 410 | `TextFormField` | `OskTextFormField` | Added |
| `lib/screens/doctor_id_page.dart` | 99 | `TextFormField` | `OskTextField` | Added |
| `lib/screens/doctor_patient_overview.dart` | 181 | `TextField` | `OskTextField` | Added |
| `lib/screens/doctor_patient_overview.dart` | 652 | `TextFormField` | `OskTextFormField` | Added |
| `lib/screens/doctor_patient_overview.dart` | 786 | `TextField` | `OskTextField` | Added |
| `lib/screens/dose_verification_page.dart` | 379 | `TextField` | `OskTextField` | Added |
| `lib/screens/dose_verification_page.dart` | 624 | `TextField` | `OskTextField` | Added |
| `lib/screens/dose_verification_page.dart` | 641 | `TextField` | `OskTextField` | Added |
| `lib/screens/dose_verification_page.dart` | 650 | `TextField` | `OskTextField` | Added |
| `lib/screens/dose_verification_page.dart` | 663 | `TextField` | `OskTextField` | Added |
| `lib/screens/dose_verification_page.dart` | 675 | `TextField` | `OskTextField` | Added |
| `lib/screens/feedback_page.dart` | 183 | `TextField` | `OskTextField` | Added |
| `lib/screens/medication_recommendation_page.dart` | 433 | `TextField` | `OskTextField` | Added |
| `lib/screens/medication_recommendation_page.dart` | 448 | `TextFormField` | `OskTextFormField` | Added |
| `lib/screens/nurse_id_page.dart` | 113 | `TextField` | `OskTextField` | Added |
| `lib/screens/nurse_patient_list_page.dart` | 106 | `TextField` | `OskTextField` | Added |
| `lib/screens/patient_portal_otp_gate.dart` | 195 | `TextField` | `OskTextField` | Added |
| `lib/screens/pharmacist_id_page.dart` | 122 | `TextField` | `OskTextField` | Added |
| `lib/screens/pharmacist_page.dart` | 144 | `TextField` | `OskTextField` | Added |
| `lib/screens/pharmacist_page.dart` | 255 | `TextField` | `OskTextField` | Added |
| `lib/screens/prescription_alert_page.dart` | 1127 | `TextField` | `OskTextField` | Added |
| `lib/screens/prescription_alert_page.dart` | 1142 | `TextField` | `OskTextField` | Added |
| `lib/screens/prescription_alert_page.dart` | 1449 | `TextField` | `OskTextField` | Added |
| `lib/widgets/review_notification_bell.dart` | 413 | `TextField` | `OskTextField` | Added |
| `lib/widgets/review_notification_bell.dart` | 573 | `TextField` | `OskTextField` | Added |
| `lib/widgets/review_notification_bell.dart` | 804 | `TextField` | `OskTextField` | Added |
| `lib/widgets/review_notification_bell.dart` | 816 | `TextField` | `OskTextField` | Added |

`lib/widgets/osk_text_field.dart` is the new shared widget file. It contains
the internal plain `TextField` implementations used by the wrappers and is
not itself a replacement site.

## Rules when re-applying

1. Do not modify `lib/screens/pi_scanner_page.dart`.
2. Do not modify `pi_scanner.py`.
3. Do not modify scanner, camera, QR-routing, or QR-input code.
4. The hidden QR-input `TextField` in `pi_scanner_page.dart` must remain a
   plain `TextField`.
5. Do not add a package or change `pubspec.yaml`.
6. Preserve existing validation, form keys, business logic, navigation,
   callbacks, controller usage, and styling.
7. Preserve all existing field parameters when changing the widget type.
8. Use `OskTextFormField` for validator-backed `TextFormField` instances;
   never drop `validator`, `autovalidateMode`, `onSaved`, or form behavior.
9. Dialog and bottom-sheet content must remain scrollable when a focused input
   could be covered by Onboard.
10. Do not use the wrapper for hidden scanner fields or other non-manual
    machine-input fields.

## Re-apply to a fresh codebase

1. Confirm the target is the Flutter Linux Raspberry Pi/X11 build and that
   Onboard is available in the user's graphical session.
2. Copy `osk_text_field.dart.txt` to
   `lib/widgets/osk_text_field.dart`, or recreate it from the source block
   above.
3. Search the entire `lib/` folder, including subfolders, dialogs, and bottom
   sheets, for all of:
   `TextField`, `TextFormField`, `EditableText`, `SearchBar`,
   `SearchAnchor`, `Autocomplete`, and `DropdownMenu`.
4. Also search for project-specific widgets that wrap a text input.
5. Mark each result as manual entry, machine/scanner input, hidden/offscreen,
   or non-input implementation detail.
6. Before editing, produce a table containing the file, line, widget type,
   dialog/sheet context, and exclusion reason where applicable.
7. Replace every non-excluded manual input with `OskTextField`.
8. Replace validator-backed `TextFormField` instances with
   `OskTextFormField`, preserving all validation and form parameters.
9. Add the relative import to every changed file.
10. Compare the supported parameters against the newer field usages. Extend
    the wrappers for any new parameters before replacing fields.
11. Check dialog and bottom-sheet layouts. Keep long content in a
    `SingleChildScrollView` or equivalent and account for view insets.
12. Re-run the complete search and confirm that only the protected scanner
    field and wrapper implementation fields remain plain.
13. Test the checklist below on the Raspberry Pi.

## Test checklist

- Tap a manual-entry field: Onboard appears.
- Tap the same field after dismissing Onboard: Onboard appears again.
- Move focus directly between two `OskTextField`/`OskTextFormField` widgets:
  the 150 ms delay prevents hide/show flicker.
- Leave a page or close a dialog: Onboard hides after the delayed focus check.
- Focus a field inside a dialog: the dialog content remains usable and
  scrolls if necessary.
- Focus a field inside a bottom sheet: the focused field is not hidden behind
  the keyboard.
- Enter text through Onboard and confirm the original callback/validation
  behavior still works.
- Open a field with prefilled controller text and submit its parent `Form`:
  the prefilled value is treated as filled.
- Disabled fields do not open Onboard.
- Read-only fields do not open Onboard for editing. If a read-only field is
  programmatically focused by a special screen, verify that behavior
  explicitly.
- Open the scanner page: its hidden QR field remains a plain `TextField` and
  Onboard is not shown for it.
- Run the QR scanner separately and verify scanner behavior is unchanged.

## Known limitations

- The wrapper controls Onboard through `dbus-send` and therefore depends on
  Onboard, a session D-Bus, and the active X11 graphical session.
- The implementation is not a general mobile/Wayland keyboard solution.
- `setOskVisible` intentionally ignores `Process.run` failures, so a missing
  Onboard installation or D-Bus failure is not surfaced in the Flutter UI.
- The wrappers expose the parameters needed by the current repository, not
  every possible `TextField`/`TextFormField` parameter. Re-check and extend
  them when applying to a newer Flutter version.
- `OskTextFormField` uses a `FormField<String>` around an internal
  `TextField`; it synchronizes controller text so asynchronously prefilled
  values validate correctly.
- The 150 ms hide timer is global to the shared widget file. It is intended
  to prevent flicker during focus transitions, but timing can still depend on
  the desktop environment.
- The camera preview is intentionally outside Flutter. The hidden QR field
  on the scanner page receives keyboard-like input from `pi_scanner.py`.
- Onboard may remain unavailable if the application is launched outside the
  user's graphical X11 session or if the process has no session D-Bus access.
