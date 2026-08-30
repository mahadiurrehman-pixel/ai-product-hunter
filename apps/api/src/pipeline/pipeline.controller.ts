import { Controller, Get, Query, UseGuards, Req } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { EngineService } from '../engine/engine.service';
import { PrismaService } from '../prisma/prisma.service';

@Controller('pipeline')
@UseGuards(AuthGuard('jwt'))
export class PipelineController {
  constructor(
    private readonly engine: EngineService,
    private readonly prisma: PrismaService,
  ) {}

  @Get('analyze')
  async analyze(
    @Query('query') query: string,
    @Query('marketplace') marketplace = 'US',
    @Query('limit') limit = '20',
    @Query('min_score') minScore = '0.60',
    @Req() req: any,
  ) {
    const results = await this.engine.runPipeline(
      query,
      marketplace,
      parseInt(limit, 10),
      parseFloat(minScore),
    );

    // Save search telemetry for active optimization
    await this.prisma.searchHistory.create({
      data: {
        userId: req.user.id,
        query,
        marketplace,
        resultsCount: results.results ? results.results.length : 0,
      },
    });

    return results;
  }
}