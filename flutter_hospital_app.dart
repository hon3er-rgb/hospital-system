import 'package:flutter/material.dart';
import 'dart:async';
import 'dart:math' as math;

void main() {
  runApp(const HospitalApp());
}

class HospitalApp extends StatelessWidget {
  const HospitalApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: Colors.black,
        primaryColor: const Color(0xFFD07AFB),
      ),
      home: const BootScreen(),
    );
  }
}

class BootScreen extends StatefulWidget {
  const BootScreen({super.key});

  @override
  _BootScreenState createState() => _BootScreenState();
}

class _BootScreenState extends State<BootScreen> with TickerProviderStateMixin {
  double _progress = 0;
  late AnimationController _rotationController;

  @override
  void initState() {
    super.initState();
    _rotationController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 10),
    )..repeat();
    
    _startBoot();
  }

  void _startBoot() {
    Timer.periodic(const Duration(milliseconds: 50), (timer) {
      setState(() {
        _progress += 0.01;
        if (_progress >= 1.0) {
          _progress = 1.0;
          timer.cancel();
          // Navigate to Login after sound
        }
      });
    });
  }

  @override
  void dispose() {
    _rotationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Stack(
              alignment: Alignment.center,
              children: [
                AnimatedBuilder(
                  animation: _rotationController,
                  builder: (context, child) {
                    return Transform.rotate(
                      angle: _rotationController.value * 2 * math.pi,
                      child: CustomPaint(
                        size: const Size(250, 250),
                        painter: CyberHudPainter(_progress),
                      ),
                    );
                  },
                ),
                Text(
                  '${(_progress * 100).toInt()}%',
                  style: const TextStyle(
                    fontSize: 48,
                    fontWeight: FontWeight.w200,
                    color: Color(0xFFD07AFB),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 50),
            const Text(
              'INITIALIZING PROTOCOL',
              style: TextStyle(
                color: Color(0xFFD07AFB),
                letterSpacing: 10,
                fontSize: 10,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class CyberHudPainter extends CustomPainter {
  final double progress;
  CyberHudPainter(this.progress);

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xFFD07AFB)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.0;

    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2;

    // Outer segments
    for (var i = 0; i < 3; i++) {
        canvas.drawArc(
            Rect.fromCircle(center: center, radius: radius),
            (i * 120 + 20) * math.pi / 180,
            80 * math.pi / 180,
            false,
            paint..strokeWidth = 8
        );
    }

    // Inner dash spinner
    final dashPaint = Paint()
      ..color = const Color(0xFFD07AFB).withOpacity(0.3)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 12.0;
    
    // Simplified representation for HUD image match
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius - 30),
      0,
      2 * math.pi,
      false,
      dashPaint..strokeDashArray = [2, 10] as List<double>? // Pseudo code
    );
  }

  @override
  bool shouldRepaint(CustomPainter oldDelegate) => true;
}
